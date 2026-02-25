# IMPORTS
import contextlib
import logging
import threading
import time
from copy import deepcopy

import requests

from chroma_models import ChromaState
from color_conversions import float_to_decimal
from effects import update_explosion_effect, update_wave_effect

logger = logging.getLogger(__name__)

class ChromaControl(requests.Session):
    """
    Custom `requests.Session` implementation to control Razer Chroma enabled devices.
    """
    def __init__(self) -> None:
        self.state = ChromaState()
        self.connected_event = threading.Event()

        super().__init__()

        effect_thread = threading.Thread(target=self.update_effects, daemon=True)
        effect_thread.start()

    def start_heartbeat(self) -> None:
        """
        Start a heartbeat to the Razer Chroma SDK in a seperate thread.
        """
        heartbeat_thread = threading.Thread(target=self.heartbeat, daemon=True)
        heartbeat_thread.start()

    def heartbeat(self) -> None:
        """
        Ping the Razer Chroma SDK every 5 seconds.
        """
        while self.connected_event.is_set():
            with contextlib.suppress(requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                self.request("PUT", self.url + "/heartbeat", timeout=0.00001)
            time.sleep(5)

    def connect(self) -> None:
        """
        Connect to the Razer Chroma SDK.
        """
        response = self.request("POST",
                     "http://localhost:54235/razer/chromasdk",
                     json={
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
                     })
        body = response.json()
        self.url: str = body["uri"]
        self.connected_event.set()
        self.start_heartbeat()
        self.state = ChromaState()

        time.sleep(2) # Give the Chroma SDK time to intialize the app before resetting the keyboard RGB
        result = self.request("PUT", self.url + "/keyboard", json={"effect": "CHROMA_NONE"}).json()

        # Check that we successfully set the keyboard's color
        if result["result"] != 0:
            self.disconnect()
            if result["result"] == 126:
                logger.error(f"Failed to set Chroma keyboard color, disconnecting from Razer Chroma SDK. This error is usually caused by having the non-BETA version of Razer Synapse 4 installed. Code: {result["result"]}")
            else:
                logger.error(f"Failed to set Chroma keyboard color, disconnecting from Razer Chroma SDK. Code: {result["result"]}")
        else:
            logger.info(f"Connected to {self.url}")

    def disconnect(self) -> None:
        """
        Disconnect from the Razer Chroma SDK.
        """
        self.connected_event.clear()
        with contextlib.suppress(requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            self.request("DELETE", self.url, timeout=0.00001)

        logger.info(f"Disconnected from {self.url}")

    def update_effects(self) -> None:
        """
        Update the keyboard's color with active effects, and update any effect animations.
        """
        while True:
            self.connected_event.wait()

            expiring_effects = []
            effect_changed = False
            with self.state.lock:
                for effect in self.state.effects:
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
                                        if color[-1] > max_value:
                                            max_value = color[-1]
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
                    self.state.effects.remove(effect)

                if not effect_changed:
                    effect_changed = self.state.effects != self.state.previous_effects
                if effect_changed:
                    self.state.previous_effects = deepcopy(self.state.effects)

                if effect_changed and len(self.state.effects) > 0:
                    colors = [[(0.0, 0.0, 0.0) for _ in range(22)] for _ in range(6)]
                    for effect in self.state.effects:
                        match effect.method:
                            case "ADD":
                                # Add everything
                                for row, row_v in enumerate(effect.colors):
                                    for column, column_v in enumerate(row_v):
                                        colors[row][column] = tuple([(colors[row][column][i] + column_v[i] if colors[row][column][i] + column_v[i] <= 1.0 else 1.0) for i in range(3)])
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
                                        colors[row][column] = tuple([(colors[row][column][i] * column_v[i] if colors[row][column][i] * column_v[i] <= 1.0 else 1.0) for i in range(3)])
                    # Convert the float colors to decimal colors usable by the Chroma SDK API
                    for row, row_v in enumerate(colors):
                        for column, column_v in enumerate(row_v):
                            colors[row][column] = float_to_decimal(column_v)

                    with contextlib.suppress(requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                        self.request("PUT",
                                     self.url + "/keyboard",
                                     json={
                                         "effect": "CHROMA_CUSTOM",
                                         "param": colors
                                         },
                                     timeout=0.00001)
                elif effect_changed:
                    with contextlib.suppress(requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                        self.request("PUT", self.url + "/keyboard", json={"effect": "CHROMA_NONE"}, timeout=0.00001)

# By @peterservices
