"""Coordinate conversion utilities (normalized 0–1 ↔ pixel)."""


def pixel_to_norm(x_px: int, y_px: int, width: int, height: int) -> tuple[float, float]:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    return x_px / width, y_px / height


def norm_to_pixel(x: float, y: float, width: int, height: int) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    return round(x * width), round(y * height)
