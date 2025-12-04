# IMPORTS
import contextlib
import threading
import time
from copy import deepcopy
from threading import Lock
from typing import Literal

import requests
from pydantic import BaseModel, ConfigDict, field_validator

from utils import float_to_decimal


class ChromaEffect(BaseModel):
    type: Literal["STATIC", "WAVE", "FIRE", "EXPLOSION"]
    method: Literal["ADD", "FILL", "FILL_EMPTY", "FILL_NO_ZERO", "MULTIPLY"]
    direction: Literal["UP", "RIGHT", "DOWN", "LEFT"] | None = None
    colors: list[list[tuple[float, float, float]]]
    decay_amount: float | None = None
    update_rate: float | None = None
    last_update: float = 0
    expires_after_updates: int | None = None
    id: str | None = None

    @field_validator("colors", mode="after")
    @classmethod
    def validate_colors_dimensions(cls, value: list[list[tuple[float, float, float]]]):
        if len(value) != 6:
            raise ValueError(f"Expected outer list to have a length of 6, got {len(value)}")
        for inner_list in value:
            if len(inner_list) != 22:
                raise ValueError(f"Expected inner list to have a length of 22, got {len(inner_list)}")

        return value

class ChromaState(BaseModel):
    model_config: ConfigDict = ConfigDict(arbitrary_types_allowed=True)

    effects: list[ChromaEffect] = []
    previous_effects: list[ChromaEffect] = []
    lock: Lock = Lock()

    def find_effect_by_id(self, id: str) -> ChromaEffect | None:
        """
        Find an effect in the active effects by its id.

        :param id: The effect id to look for.

        :return: The `ChromaEffect`, if found, or None.
        """
        for effect in self.effects:
            if effect.id == id:
                return effect
        return None

    def add_effect(self, effect: ChromaEffect) -> None:
        """
        Add an effect to the effects list, respecting hierarchy. If an effect does not have a valid id, it will be treated as highest hierarchy.

        :param effect: The effect to be added to the active effects.
        """
        effect_id_hierarchy = [ # Lowest to highest
            "movement_key_indicator",
            "interaction_key_indicator",
            "inventory_key_indicator",
            "smoke",
            "fire",
            "flash",
            "kill",
            "shoot",
            "death",
            "defusal_indicator",
            "bomb",
            "result"
        ]
        if effect.id is not None and len(self.effects) > 0 and effect.id in effect_id_hierarchy:
            highest_available_index = 0
            for id in effect_id_hierarchy:
                if id == effect.id:
                    with self.lock:
                        self.effects.insert(highest_available_index, effect)
                    return

                found_effect = self.find_effect_by_id(id)
                if found_effect is not None:
                    highest_available_index = self.effects.index(found_effect) + 1

                    # There is no point in checking the rest of the hierarchy if no other effects are in the list
                    if highest_available_index == len(self.effects):
                        with self.lock:
                            self.effects.append(effect)
                        return
        else:
            with self.lock:
                self.effects.append(effect)

    def remove_effect(self, effect: ChromaEffect) -> None:
        """
        Remove an effect from the effects list.

        :param effect: The effect to be added to the active effects.
        """
        if effect in self.effects:
            with self.lock:
                self.effects.remove(effect)

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
                print(f"[CHROMA] Failed to set Chroma keyboard color, disconnecting from Razer Chroma SDK. This error is usually caused by having the non-BETA version of Razer Synapse 4 installed. Code: {result["result"]}")
            else:
                print(f"[CHROMA] Failed to set Chroma keyboard color, disconnecting from Razer Chroma SDK. Code: {result["result"]}")
        else:
            print(f"[CHROMA] Connected to {self.url}")

    def disconnect(self) -> None:
        """
        Disconnect from the Razer Chroma SDK.
        """
        self.connected_event.clear()
        with contextlib.suppress(requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            self.request("DELETE", self.url, timeout=0.00001)

        print(f"[CHROMA] Disconnected from {self.url}")

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
                                match effect.direction:
                                    case "UP":
                                        first = effect.colors.pop(0)
                                        effect.colors.append(first)
                                    case "RIGHT":
                                        for _, v in enumerate(effect.colors):
                                            last = v.pop()
                                            v.insert(0, last)
                                    case "DOWN":
                                        last = effect.colors.pop()
                                        effect.colors.insert(0, last)
                                    case "LEFT":
                                        for _, v in enumerate(effect.colors):
                                            first = v.pop(0)
                                            v.append(first)
                            case "FIRE":
                                effect_changed = True
                                pass
                            case "EXPLOSION":
                                effect_changed = True

                                # Expand left half
                                for i in range(2, 4):
                                    explosion_color = effect.colors[i][10]
                                    index = effect.colors[i].index(explosion_color, 0, 11)
                                    if index != 0:
                                        effect.colors[i][index - 1] = explosion_color

                                    if i == 2:
                                        first = 0
                                        second = 1
                                    else:
                                        first = 4
                                        second = 5
                                    try:
                                        index = effect.colors[first].index(explosion_color, 0, 11)
                                        if index != 0:
                                            effect.colors[first][index - 1] = explosion_color

                                        try:
                                            index = effect.colors[second].index(explosion_color, 0, 11)
                                            if index != 0:
                                                effect.colors[second][index - 1] = explosion_color
                                        except ValueError:
                                            effect.colors[second][10] = explosion_color
                                    except ValueError:
                                        effect.colors[first][10] = explosion_color

                                # Expand right half
                                for i in range(2, 4):
                                    explosion_color = effect.colors[i][11]
                                    index = 21 - effect.colors[i][::-1].index(explosion_color, 0, 11)
                                    if index != 21:
                                        effect.colors[i][index + 1] = explosion_color

                                    if i == 2:
                                        first = 0
                                        second = 1
                                    else:
                                        first = 4
                                        second = 5
                                    try:
                                        index = 21 - effect.colors[first][::-1].index(explosion_color, 0, 11)
                                        if index != 21:
                                            effect.colors[first][index + 1] = explosion_color

                                        try:
                                            index = 21 - effect.colors[second][::-1].index(explosion_color, 0, 11)
                                            if index != 21:
                                                effect.colors[second][index + 1] = explosion_color
                                        except ValueError:
                                            effect.colors[second][11] = explosion_color
                                    except ValueError:
                                        effect.colors[first][11] = explosion_color
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
