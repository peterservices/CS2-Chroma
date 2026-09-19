# IMPORTS
import json
import logging
import threading
import time
from copy import deepcopy

import websocket

from chroma_models import ChromaState
from color_conversions import float_to_decimal
from effects import update_explosion_effect, update_wave_effect

logger = logging.getLogger(__name__)

WEBSOCKET_URI = "ws://localhost:13337/razer/chromasdk"

class ChromaControl(websocket.WebSocket):
    """
    Custom `websocket.WebSocket` implementation to control Razer Chroma enabled devices.
    """
    def __init__(self) -> None:
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
        self.send(json.dumps({
            "title": "Counter-Strike 2 Razer Chroma Integration",
            "description": "Get RGB feedback to actions in-game!",
            "author": {
                "name": "Ticataco",
                "contact": "https://discord.gg/MPPvzQK2zk"
            },
            "device_supported": [
                "keyboard"
            ],
            "category": "application"
        }))
        self.chroma_connected_event.set()
        self.chroma_state = ChromaState()

        time.sleep(2) # Give the Chroma SDK time to intialize the app before resetting the keyboard RGB
        self.send(json.dumps({"endpoint": "keyboard", "effect": "CHROMA_NONE"}))
        logger.info(f"Connected to {WEBSOCKET_URI}")

    def chroma_disconnect(self) -> None:
        """
        Disconnect from the Razer Chroma SDK.
        """
        self.chroma_connected_event.clear()
        self.close()

        logger.info(f"Disconnected from {WEBSOCKET_URI}")

    def chroma_update_effects(self) -> None:
        """
        Update the keyboard's color with active effects, and update any effect animations.
        """
        while True:
            self.chroma_connected_event.wait()

            expiring_effects = []
            effect_changed = False
            with self.chroma_state.lock:
                for effect in self.chroma_state.effects:
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
                    self.chroma_state.effects.remove(effect)

                if not effect_changed:
                    effect_changed = self.chroma_state.effects != self.chroma_state.previous_effects
                if effect_changed:
                    self.chroma_state.previous_effects = deepcopy(self.chroma_state.effects)

                if effect_changed and len(self.chroma_state.effects) > 0:
                    colors = [[(0.0, 0.0, 0.0) for _ in range(24)] for _ in range(8)]
                    for effect in self.chroma_state.effects:
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

                    self.send(json.dumps({
                        "endpoint": "keyboard",
                        "effect": "CHROMA_CUSTOM2",
                        "param": {
                           "color": colors,
                           "key": [[0 for _ in range(22)] for _ in range(6)] # Make key param all zeros because it's not needed
                        }
                    }))
                elif effect_changed:
                    self.send(json.dumps({
                        "endpoint": "keyboard",
                        "effect": "CHROMA_NONE"
                    }))

# By @peterservices
