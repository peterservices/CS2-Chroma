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
    win_team: str | None = None
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
    smoke_effect:bool = True
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

def rgb_to_float(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """
    Converts an RGB color to a float color.
    """
    rgb_float = []
    for color in rgb:
        rgb_float.append(color/255)
    return tuple(rgb_float)

def float_to_rgb(rgb_float: tuple[float, float, float]) -> tuple[int, int, int]:
    """
    Converts a float color to an RGB color.
    """
    rgb = []
    for color in rgb_float:
        rgb.append(int(round(color*255, 0)))
    return tuple(rgb)

def rgb_to_decimal(rgb: tuple[int, int, int]) -> int:
    """
    Converts an RGB color to a decimal color in BGR format.
    """
    return rgb[2] * 65536 + rgb[1] * 256 + rgb[0]

def decimal_to_rgb(decimal: int) -> tuple[int, int, int]:
    """
    Converts a decimal color in BGR format to an RGB color.
    """
    blue = decimal / 65536
    green = (decimal - blue * 65536) / 256
    red = decimal - blue * 65536 - green * 256
    return (int(round(red, 0)), int(round(green, 0)), int(round(blue, 0)))

def float_to_decimal(rgb_float: tuple[float, float, float]) -> int:
    """
    Converts a float color to a decimal color in BGR format.
    """
    return rgb_to_decimal(float_to_rgb(rgb_float))

def decimal_to_float(decimal: int) -> tuple[float, float, float]:
    """
    Converts a decimal color in BGR format to a float color.
    """
    return rgb_to_float(decimal_to_rgb(decimal))

def create_wave_effect(colors: list[tuple[int]], line_orientation: Literal["VERTICAL", "HORIZONTAL"], mode: Literal["ALTERNATING", "CLUSTER"]) -> list[list[tuple[float, float, float]]]:
    """
    Creates a matrix of float colors to be used for a wave effect using the supplied colors in RGB format.

    `VERTICAL`: Max 22 colors.
    `HORIZONTAL`: Max 6 colors.

    `ALTERNATING`: Colors repeat seperated. (Looks best when the number of colors is a factor of the max colors.)
    `CLUSTER`: Colors repeat clumped with themselves.
    """
    if len(colors) < 2:
        raise ValueError(f"Expected `colors` to have a length no less than 2, got {len(colors)}")
    if line_orientation == "VERTICAL" and len(colors) > 22:
        raise ValueError(f"Expected `colors` to have a length no greater than 22, got {len(colors)}")
    if line_orientation == "HORIZONTAL" and len(colors) > 6:
        raise ValueError(f"Expected `colors` to have a length no greater than 6, got {len(colors)}")

    float_colors = [rgb_to_float(v) for v in colors]

    match line_orientation:
        case "VERTICAL":
            row_pattern = float_colors.copy()
            color = 0
            match mode:
                case "ALTERNATING":
                    while len(row_pattern) < 22:
                        row_pattern.append(float_colors[color])
                        color += 1
                        if color >= len(float_colors):
                            color = 0
                case "CLUSTER":
                    while len(row_pattern) < 22:
                        index = row_pattern.index(float_colors[color])
                        row_pattern.insert(index, float_colors[color])
                        color += 1
                        if color >= len(float_colors):
                            color = 0
            pattern = [row_pattern for _ in range(6)]
        case "HORIZONTAL":
            column_pattern = float_colors.copy()
            color = 0
            match mode:
                case "ALTERNATING":
                    while len(column_pattern) < 6:
                        column_pattern.append(float_colors[color])
                        color += 1
                        if color >= len(float_colors):
                            color = 0
                case "CLUSTER":
                    while len(column_pattern) < 6:
                        index = column_pattern.index(float_colors[color])
                        column_pattern.insert(index, float_colors[color])
                        color += 1
                        if color >= len(float_colors):
                            color = 0
            pattern = [[color] for color in column_pattern]
            for i in range(len(pattern)):
                pattern[i] = [pattern[i][0] for _ in range(22)]
    return pattern

def create_explosion_effect(color: tuple[int]) -> list[list[tuple[float, float, float]]]:
    """
    Creates a matrix of float colors to be used for an explosion effect using the supplied color in RGB format.
    """
    float_color = rgb_to_float(color)

    # Make a blank background
    pattern = [[(0.0, 0.0, 0.0) for _ in range(22)] for _ in range(6)]

    # Create a 2x2 colored square in the center of the matrix
    pattern[2][10] = float_color
    pattern[2][11] = float_color
    pattern[3][10] = float_color
    pattern[3][11] = float_color

    return pattern
# By @peterservices
