# IMPORTS
from copy import deepcopy
from threading import Lock
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

type DEVICE_TYPE = Literal["KEYBOARD", "MOUSE", "HEADSET"]

class ChromaEffect(BaseModel):
    """
    Base Chroma effect.
    """
    method: Literal["ADD", "FILL", "FILL_EMPTY", "FILL_NO_ZERO", "MULTIPLY"]
    type: Literal["STATIC"] = "STATIC"
    colors: list[list[tuple[float, float, float]]]
    decay_amount: float | None = None
    update_rate: float | None = None
    last_update: float = 0
    expires_after_updates: int | None = None
    id: str | None = None

class ChromaKeyboardEffect(ChromaEffect):
    """
    Keyboard Chroma effect.

    colors: 8 x 24 list
    """
    type: Literal["STATIC", "WAVE", "EXPLOSION"]
    direction: Literal["UP", "RIGHT", "DOWN", "LEFT"] | None = None

    @field_validator("colors", mode="after")
    @classmethod
    def validate_colors_dimensions(cls, value: list[list[tuple[float, float, float]]]) -> list[list[tuple[float, float, float]]]:
        if len(value) != 8:
            raise ValueError(f"Expected outer list to have a length of 8, got {len(value)}")
        for inner_list in value:
            if len(inner_list) != 24:
                raise ValueError(f"Expected inner list to have a length of 24, got {len(inner_list)}")

        return value

class ChromaMouseEffect(ChromaEffect):
    """
    Mouse Chroma effect.

    colors: 1 x 1 list
    """
    @field_validator("colors", mode="after")
    @classmethod
    def validate_colors_dimensions(cls, value: list[list[tuple[float, float, float]]]) -> list[list[tuple[float, float, float]]]:
        if len(value) != 1:
            raise ValueError(f"Expected outer list to have a length of 1, got {len(value)}")
        for inner_list in value:
            if len(inner_list) != 1:
                raise ValueError(f"Expected inner list to have a length of 1, got {len(inner_list)}")

        return value

class ChromaHeadsetEffect(ChromaEffect):
    """
    Headset Chroma effect.

    colors: 1 x 1 list
    """
    @field_validator("colors", mode="after")
    @classmethod
    def validate_colors_dimensions(cls, value: list[list[tuple[float, float, float]]]) -> list[list[tuple[float, float, float]]]:
        if len(value) != 1:
            raise ValueError(f"Expected outer list to have a length of 1, got {len(value)}")
        for inner_list in value:
            if len(inner_list) != 1:
                raise ValueError(f"Expected inner list to have a length of 1, got {len(inner_list)}")

        return value

class ChromaState(BaseModel):
    model_config: ConfigDict = ConfigDict(arbitrary_types_allowed=True)

    keyboard_effects: list[ChromaKeyboardEffect] = []
    previous_keyboard_effects: list[ChromaKeyboardEffect] = []

    mouse_effects: list[ChromaMouseEffect] = []
    previous_mouse_effects: list[ChromaMouseEffect] = []

    headset_effects: list[ChromaHeadsetEffect] = []
    previous_headset_effects: list[ChromaHeadsetEffect] = []

    lock: Lock = Lock()

    def find_effect_by_id(self, id: str, device: DEVICE_TYPE) -> ChromaKeyboardEffect | ChromaMouseEffect | ChromaHeadsetEffect | None:
        """
        Find an effect in the specified effects list by its id.

        Args:
            id: The effect id to look for.
            device: The device type of the effect to look for.

        Returns:
            The `ChromaEffect` subclass, if found, or None.
        """
        effects = self.get_effects_list_from_device_type(device)

        for effect in effects:
            if effect.id == id:
                return effect
        return None

    def add_effect(self, effect: ChromaKeyboardEffect | ChromaMouseEffect | ChromaHeadsetEffect) -> None:
        """
        Add an effect to the effects list, respecting hierarchy. If an effect does not have a valid id, it will be treated as highest hierarchy.

        Args:
            effect: The effect to be added to the active effects.
        """
        effects, device = self.get_effects_list_from_effect_type(effect)

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
        if effect.id is not None and len(effects) > 0 and effect.id in effect_id_hierarchy:
            highest_available_index = 0
            for id in effect_id_hierarchy:
                if id == effect.id:
                    effects.insert(highest_available_index, effect)
                    return

                found_effect = self.find_effect_by_id(id, device)
                if found_effect is not None:
                    highest_available_index = effects.index(found_effect) + 1

                    # There is no point in checking the rest of the hierarchy if no other effects are in the list
                    if highest_available_index == len(effects):
                        effects.append(effect)
                        return
        else:
            effects.append(effect)

    def remove_effect(self, effect: ChromaKeyboardEffect | ChromaMouseEffect | ChromaHeadsetEffect) -> None:
        """
        Remove an effect from the effects list.

        Args:
            effect: The effect to be removed from the active effects.
        """
        effects, _ = self.get_effects_list_from_effect_type(effect)

        if effect in effects:
            effects.remove(effect)

    def remove_effects_by_id(self, id: str, devices: list[DEVICE_TYPE]) -> None:
        """
        Remove effects from the specified effects lists by their ids.

        Args:
            id: The effect id to look for.
            devices: The device types of the effects to remove.
        """
        for device_type in devices:
            effect = self.find_effect_by_id(id, device_type)
            if effect is not None:
                self.remove_effect(effect)

    def remove_player_effects(self) -> None:
        """
        Remove in-game player specific effects from all effects list.
        """
        effect_ids: list[str] = ["death", "kill", "flash", "smoke", "fire", "shoot"]
        for id in effect_ids:
            self.remove_effects_by_id(id, ["KEYBOARD", "MOUSE", "HEADSET"])

    def get_previous_effects(self, device: DEVICE_TYPE) -> list[ChromaKeyboardEffect | ChromaMouseEffect | ChromaHeadsetEffect]:
        """
        Get a previously backed up copy of the specified effects list.
        """
        match device:
            case "KEYBOARD":
                return self.previous_keyboard_effects
            case "MOUSE":
                return self.previous_mouse_effects
            case "HEADSET":
                return self.previous_headset_effects
            case _:
                raise ValueError(f"Unexpected device of {device}")

    def save_previous_effects(self, device: DEVICE_TYPE) -> None:
        """
        Save a deep copy of the specified effects list.
        """
        effects = self.get_effects_list_from_device_type(device)

        match device:
            case "KEYBOARD":
                self.previous_keyboard_effects = deepcopy(effects)
            case "MOUSE":
                self.previous_mouse_effects = deepcopy(effects)
            case "HEADSET":
                self.previous_headset_effects = deepcopy(effects)
            case _:
                raise ValueError(f"Unexpected device of {device}")

    def get_effects_list_from_device_type(self, device: DEVICE_TYPE) -> list[ChromaKeyboardEffect | ChromaMouseEffect | ChromaHeadsetEffect]:
        """
        Get the corresponding effects list from the device type.
        """
        match device:
            case "KEYBOARD":
                return self.keyboard_effects
            case "MOUSE":
                return self.mouse_effects
            case "HEADSET":
                return self.headset_effects
            case _:
                raise ValueError(f"Unexpected device of {device}")

    def get_effects_list_from_effect_type(self, effect: ChromaKeyboardEffect | ChromaMouseEffect | ChromaHeadsetEffect) -> tuple[list[ChromaKeyboardEffect | ChromaMouseEffect | ChromaHeadsetEffect], DEVICE_TYPE]:
        """
        Get the corresponding effects list and device type from the effect type.
        """
        if isinstance(effect, ChromaKeyboardEffect):
            return (self.keyboard_effects, "KEYBOARD")
        if isinstance(effect, ChromaMouseEffect):
            return (self.mouse_effects, "MOUSE")
        if isinstance(effect, ChromaHeadsetEffect):
            return (self.headset_effects, "HEADSET")
        raise TypeError("Expected either a Chroma keyboard or mouse effect.")

# By @peterservices
