# IMPORTS
from threading import Lock
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class ChromaEffect(BaseModel):
    type: Literal["STATIC", "WAVE", "EXPLOSION"]
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

    def remove_player_effects(self):
        """
        Remove in-game player specific effects from the effects list.
        """
        effect_ids: list[str] = ["death", "kill", "flash", "smoke", "fire", "shoot"]
        for id in effect_ids:
            effect = self.find_effect_by_id(id)
            if effect is not None:
                self.remove_effect(effect)

# By @peterservices
