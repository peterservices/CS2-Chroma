# IMPORTS
from typing import Literal

from pydantic import BaseModel


class Weapon(BaseModel):
    name: str
    type: str | None
    ammo_clip: int | None
    ammo_clip_max: int | None
    ammo_reserve: int | None
    active: bool

class PlayerState(BaseModel):
    weapons: dict[str, Weapon] = {}
    health: int = 0
    armor_health: int = 0
    money: int = 0
    round_kills: int = 0
    round_headshot_kills: int = 0
    equipment_value: int = 0
    has_helmet: bool = False
    is_flashed: bool = False
    in_smoke: bool = False
    is_burning: bool = False

class PlayerStatistics(BaseModel):
    kills: int = 0
    assists: int = 0
    deaths: int = 0
    mvps: int = 0
    score: int = 0

class Player(BaseModel):
    steam_id: str = ""
    name: str = ""
    team: Literal["CT", "T"] | None = None
    state: PlayerState = PlayerState()
    statistics: PlayerStatistics = PlayerStatistics()

class Team(BaseModel):
    score: int = 0
    timeouts: int = 0

class Map(BaseModel):
    mode: str = ""
    name: str = ""
    phase: str = ""
    round: str = ""
    ct_team: Team = Team()
    t_team: Team = Team()

class Round(BaseModel):
    phase: str = ""
    win_team: Literal["CT", "T"] | None = None
    bomb: str | None = None
    bomb_plant_time: float | None = None

class GameState(BaseModel):
    map: Map | None = None
    round: Round | None = None
    player: Player | None = None
    steam_id: str = ""
    last_heartbeat: float = 0

class EffectConfiguration(BaseModel):
    shoot_effect: bool = True
    kill_effect: bool = True
    smoke_effect: bool = True
    burning_effect: bool = True
    flash_effect: bool = True
    death_effect: bool = True
    bomb_explosion_effect: bool = True
    game_result_effect: bool = True

class Configuration(BaseModel):
    show_effects_for_others: bool = True
    close_after_game_close: bool = False
    effects: EffectConfiguration = EffectConfiguration()
    defusal_indicator: bool = False
    movement_key_indicators: bool = True
    inventory_key_indicators: bool = True
    interaction_key_indicators: bool = False

# By @peterservices
