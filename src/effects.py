# IMPORTS
from typing import Literal

from chroma_models import ChromaEffect
from color_conversions import rgb_to_float


def create_wave_effect(colors: list[tuple[int, int, int]], line_orientation: Literal["VERTICAL", "HORIZONTAL"], mode: Literal["ALTERNATING", "CLUSTER"]) -> list[list[tuple[float, float, float]]]:
    """
    Create a matrix of float colors to be used for a wave effect using the supplied colors in RGB format.

    :param colors: List of RGB colors to be used to create the effect.

    :param line_orientation: `VERTICAL`: Max 24 colors.
    `HORIZONTAL`: Max 8 colors.

    :param mode: `ALTERNATING`: Colors repeat seperated. (Looks best when the number of colors is a factor of the max colors.)
    `CLUSTER`: Colors repeat clumped with themselves.

    :return: The generated wave effect.
    """
    if len(colors) < 2:
        raise ValueError(f"Expected `colors` to have a length no less than 2, got {len(colors)}")
    if line_orientation == "VERTICAL" and len(colors) > 24:
        raise ValueError(f"Expected `colors` to have a length no greater than 24, got {len(colors)}")
    if line_orientation == "HORIZONTAL" and len(colors) > 8:
        raise ValueError(f"Expected `colors` to have a length no greater than 8, got {len(colors)}")

    float_colors = [rgb_to_float(v) for v in colors]

    match line_orientation:
        case "VERTICAL":
            row_pattern = float_colors.copy()
            color = 0
            match mode:
                case "ALTERNATING":
                    while len(row_pattern) < 24:
                        row_pattern.append(float_colors[color])
                        color += 1
                        if color >= len(float_colors):
                            color = 0
                case "CLUSTER":
                    while len(row_pattern) < 24:
                        index = row_pattern.index(float_colors[color])
                        row_pattern.insert(index, float_colors[color])
                        color += 1
                        if color >= len(float_colors):
                            color = 0
            pattern = [row_pattern for _ in range(8)]
        case "HORIZONTAL":
            column_pattern = float_colors.copy()
            color = 0
            match mode:
                case "ALTERNATING":
                    while len(column_pattern) < 8:
                        column_pattern.append(float_colors[color])
                        color += 1
                        if color >= len(float_colors):
                            color = 0
                case "CLUSTER":
                    while len(column_pattern) < 8:
                        index = column_pattern.index(float_colors[color])
                        column_pattern.insert(index, float_colors[color])
                        color += 1
                        if color >= len(float_colors):
                            color = 0
            pattern = [[color] for color in column_pattern]
            for i in range(len(pattern)):
                pattern[i] = [pattern[i][0] for _ in range(24)]
    return pattern

def create_explosion_effect(color: tuple[int, int, int]) -> list[list[tuple[float, float, float]]]:
    """
    Create a matrix of float colors to be used for an explosion effect using the supplied color in RGB format.

    :param color: The RGB color to be used for the effect.

    :return: The generated explosion effect.
    """
    float_color = rgb_to_float(color)

    # Make a blank background
    pattern = [[(0.0, 0.0, 0.0) for _ in range(24)] for _ in range(8)]

    # Create a 2x2 colored square in the center of the matrix
    pattern[3][11] = float_color
    pattern[3][12] = float_color
    pattern[4][11] = float_color
    pattern[4][12] = float_color

    return pattern

def update_wave_effect(effect: ChromaEffect) -> None:
    """
    Update a wave effect's colors.

    :param effect: The effect to be updated.
    """
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

def update_explosion_effect(effect: ChromaEffect) -> None:
    """
    Update an explosion effect's colors.

    :param effect: The effect to be updated
    """
    # Expand left half
    for i in range(3, 5):
        explosion_color = effect.colors[i][11]
        index = effect.colors[i].index(explosion_color, 0, 12)
        if index != 0:
            effect.colors[i][index - 1] = explosion_color

        if i == 3:
            first = 2
            second = 1
            third = 0
        else:
            first = 5
            second = 6
            third = 7
        try:
            index = effect.colors[first].index(explosion_color, 0, 12)
            if index != 0:
                effect.colors[first][index - 1] = explosion_color

            try:
                index = effect.colors[second].index(explosion_color, 0, 12)
                if index != 0:
                    effect.colors[second][index - 1] = explosion_color

                try:
                    index = effect.colors[third].index(explosion_color, 0, 12)
                    if index != 0:
                        effect.colors[third][index - 1] = explosion_color
                except ValueError:
                    effect.colors[third][11] = explosion_color
            except ValueError:
                effect.colors[second][11] = explosion_color
        except ValueError:
            effect.colors[first][11] = explosion_color

    # Expand right half
    for i in range(3, 5):
        explosion_color = effect.colors[i][12]
        index = 23 - effect.colors[i][::-1].index(explosion_color, 0, 12)
        if index != 23:
            effect.colors[i][index + 1] = explosion_color

        if i == 3:
            first = 2
            second = 1
            third = 0
        else:
            first = 5
            second = 6
            third = 7
        try:
            index = 23 - effect.colors[first][::-1].index(explosion_color, 0, 12)
            if index != 23:
                effect.colors[first][index + 1] = explosion_color

            try:
                index = 23 - effect.colors[second][::-1].index(explosion_color, 0, 12)
                if index != 23:
                    effect.colors[second][index + 1] = explosion_color

                try:
                    index = 23 - effect.colors[third][::-1].index(explosion_color, 0, 12)
                    if index != 23:
                        effect.colors[third][index + 1] = explosion_color
                except ValueError:
                    effect.colors[third][12] = explosion_color
            except ValueError:
                effect.colors[second][12] = explosion_color
        except ValueError:
            effect.colors[first][12] = explosion_color

# By @peterservices
