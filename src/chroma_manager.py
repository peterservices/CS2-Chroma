# IMPORTS
import json
import logging
import threading
import time
from copy import deepcopy
from typing import Any

import websocket

from chroma_models import ChromaState
from color_conversions import float_to_decimal
from effects import update_explosion_effect, update_wave_effect
from utils import Configuration

logger = logging.getLogger(__name__)

WEBSOCKET_URI = "ws://localhost:13337/razer/chromasdk"

class ChromaControl(websocket.WebSocket):
    """
    Custom `websocket.WebSocket` implementation to control Razer Chroma enabled devices.
    """
    def __init__(self, config: Configuration) -> None:
        self.config = config
        self.chroma_state = ChromaState()
        self.chroma_connected_event = threading.Event()

        super().__init__()

        chroma_effect_thread = threading.Thread(target=self.chroma_update_effects, daemon=True)
        chroma_effect_thread.start()

    def chroma_connect(self) -> None:
        """
        Connect to the Razer Chroma SDK.
        """
        self.connect(WEBSOCKET_URI)
        self.chroma_send({
            "title": "Counter-Strike 2 Razer Chroma Integration",
            "description": "Get RGB feedback to actions in-game!",
            "author": {
                "name": "Ticataco",
                "contact": "https://github.com/peterservices/CS2-Chroma/issues"
            },
            "device_supported": [
                "keyboard",
                "mouse",
                "headset"
            ],
            "category": "application"
        })

        time.sleep(2) # Give the Chroma SDK time to intialize the app before resetting the keyboard RGB
        for device, enabled in self.config.devices:
            if not enabled:
                continue
            self.chroma_send({"endpoint": device, "effect": "CHROMA_NONE"}) # Clear Chroma effects for all active devices

        self.chroma_connected_event.set()
        self.chroma_state = ChromaState()
        logger.info(f"Connected to {WEBSOCKET_URI}")

    def chroma_disconnect(self) -> None:
        """
        Disconnect from the Razer Chroma SDK.
        """
        self.chroma_connected_event.clear()
        self.close()

        logger.info(f"Disconnected from {WEBSOCKET_URI}")

    def chroma_send(self, payload: Any, *, try_reconnect: bool = True) -> bool:
        """
        Send data through the Razer Chroma SDK.

        Args:
            try_reconnect: Whether a reconnection should be attempted if the websocket is closed unexpectedly.

        Returns:
            Whether the payload was sent successfully.
        """
        try:
            self.send(json.dumps(payload))
            return True
        except (ConnectionError, websocket.WebSocketConnectionClosedException):
            if try_reconnect and self.chroma_connected_event.is_set():
                self.chroma_disconnect()
                self.chroma_connect()
                return self.chroma_send(payload, try_reconnect=False)
        return False

    def chroma_update_effects(self) -> None:
        """
        Update the keyboard's color with active effects, and update any effect animations.
        """
        while True:
            for device, enabled in self.config.devices:
                if not enabled:
                    continue
                device = device.upper()

                effects = self.chroma_state.get_effects_list_from_device_type(device)
                match device:
                    case "KEYBOARD":
                        device_color_columns = 24
                        device_color_rows = 8
                    case _:
                        device_color_columns = 1
                        device_color_rows = 1

                expiring_effects = []
                effect_changed = False
                with self.chroma_state.lock:
                    for effect in effects:
                        if effect.update_rate is not None and time.time() - effect.last_update >= effect.update_rate:
                            if effect.expires_after_updates is not None:
                                if effect.expires_after_updates == 0:
                                    expiring_effects.append(effect)
                                    continue
                                effect.expires_after_updates -= 1

                            if effect.decay_amount is not None:
                                effect_changed = True
                                max_value = 0.0
                                for _, row_v in enumerate(effect.colors):
                                    for column, column_v in enumerate(row_v):
                                        color: list[float] = []
                                        for i in range(3):
                                            color.append((column_v[i] - effect.decay_amount) if column_v[i] >= effect.decay_amount else 0)
                                            max_value = max(max_value, color[-1])
                                        row_v[column] = tuple(color)
                                if effect.expires_after_updates is None and max_value == 0.0:
                                    expiring_effects.append(effect)
                                    continue

                            match effect.type:
                                case "WAVE":
                                    effect_changed = True
                                    update_wave_effect(effect)
                                case "EXPLOSION":
                                    effect_changed = True
                                    update_explosion_effect(effect)
                            effect.last_update = time.time()
                    for effect in expiring_effects:
                        self.chroma_state.remove_effect(effect)

                    if not effect_changed:
                        effect_changed = effects != self.chroma_state.get_previous_effects(device)
                    if effect_changed:
                        self.chroma_state.save_previous_effects(device)

                    if effect_changed and len(effects) > 0:
                        colors = [[(0.0, 0.0, 0.0) for _ in range(device_color_columns)] for _ in range(device_color_rows)]
                        for effect in effects:
                            match effect.method:
                                case "ADD":
                                    # Add everything
                                    for row, row_v in enumerate(effect.colors):
                                        for column, column_v in enumerate(row_v):
                                            colors[row][column] = tuple([min(colors[row][column][i] + column_v[i], 1.0) for i in range(3)])
                                case "FILL":
                                    # Fill everything
                                    colors = deepcopy(effect.colors)
                                case "FILL_EMPTY":
                                    # Fill only remaining zero values
                                    for row, row_v in enumerate(effect.colors):
                                        for column, column_v in enumerate(row_v):
                                            if colors[row][column] == (0.0, 0.0, 0.0):
                                                colors[row][column] = column_v
                                case "FILL_NO_ZERO":
                                    # Fill everything, but don't fill with zero values
                                    for row, row_v in enumerate(effect.colors):
                                        for column, column_v in enumerate(row_v):
                                            if column_v != (0.0, 0.0, 0.0):
                                                colors[row][column] = column_v
                                case "MULTIPLY":
                                    # Multiply everything
                                    for row, row_v in enumerate(effect.colors):
                                        for column, column_v in enumerate(row_v):
                                            colors[row][column] = tuple([min(colors[row][column][i] * column_v[i], 1.0) for i in range(3)])
                        # Convert the float colors to decimal colors usable by the Chroma SDK API
                        for row, row_v in enumerate(colors):
                            for column, column_v in enumerate(row_v):
                                colors[row][column] = float_to_decimal(column_v)

                        if self.chroma_connected_event.is_set(): # Only send data if we are connected
                            match device:
                                case "KEYBOARD":
                                    self.chroma_send({
                                        "endpoint": "keyboard",
                                        "effect": "CHROMA_CUSTOM2",
                                        "param": {
                                           "color": colors,
                                           "key": [[0 for _ in range(22)] for _ in range(6)] # Make key param all zeros because it's not needed
                                        }
                                    })
                                case _:
                                    self.chroma_send({
                                        "endpoint": device.lower(),
                                        "effect": "CHROMA_STATIC",
                                        "param": {
                                            "color": colors[0][0]
                                        }
                                    })
                    elif effect_changed:
                        if self.chroma_connected_event.is_set(): # Only send data if we are connected
                            self.chroma_send({
                                "endpoint": device.lower(),
                                "effect": "CHROMA_NONE"
                            })

# By @peterservices
