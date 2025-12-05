def rgb_to_float(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """
    Convert an RGB color to a float color.
    """
    return tuple(color / 255 for color in rgb)

def float_to_rgb(rgb_float: tuple[float, float, float]) -> tuple[int, int, int]:
    """
    Convert a float color to an RGB color.
    """
    return tuple(int(round(color * 255)) for color in rgb_float)

def rgb_to_decimal(rgb: tuple[int, int, int]) -> int:
    """
    Convert an RGB color to a decimal color in BGR format.
    """
    return rgb[2] * 65536 + rgb[1] * 256 + rgb[0]

def decimal_to_rgb(decimal: int) -> tuple[int, int, int]:
    """
    Convert a decimal color in BGR format to an RGB color.
    """
    blue = decimal / 65536
    green = (decimal - blue * 65536) / 256
    red = decimal - blue * 65536 - green * 256
    return (int(round(red, 0)), int(round(green, 0)), int(round(blue, 0)))

def float_to_decimal(rgb_float: tuple[float, float, float]) -> int:
    """
    Convert a float color to a decimal color in BGR format.
    """
    return rgb_to_decimal(float_to_rgb(rgb_float))

def decimal_to_float(decimal: int) -> tuple[float, float, float]:
    """
    Convert a decimal color in BGR format to a float color.
    """
    return rgb_to_float(decimal_to_rgb(decimal))

# By @peterservices
