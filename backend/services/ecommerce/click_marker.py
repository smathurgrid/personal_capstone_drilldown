"""Draw click markers on outfit images."""

from PIL import ImageDraw


def draw_click_marker(image, x_norm: float, y_norm: float):
    draw = ImageDraw.Draw(image)
    width, height = image.size
    cx, cy = x_norm * width, y_norm * height
    radius = 12
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius], outline="red", width=3
    )
    dot_radius = 4
    draw.ellipse(
        [cx - dot_radius, cy - dot_radius, cx + dot_radius, cy + dot_radius], fill="red"
    )
    return image
