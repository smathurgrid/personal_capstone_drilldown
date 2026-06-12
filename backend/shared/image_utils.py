"""Image encoding helpers for the vision → generation adapter."""

import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw


def pil_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def path_to_b64(path: str | Path) -> str:
    with Image.open(path) as img:
        return pil_to_b64(img.convert("RGB"))


def b64_to_file(b64: str, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = base64.b64decode(b64)
    with Image.open(io.BytesIO(data)) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(output_path, "PNG")
    return output_path


def crop_norm_region(image_path: str, x: float, y: float, radius_ratio: float = 0.12) -> str:
    """Crop a square region around normalized (x,y); returns base64 PNG."""
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        w, h = img.size
        cx, cy = int(x * w), int(y * h)
        radius = max(40, int(min(w, h) * radius_ratio))
        x1 = max(0, cx - radius)
        y1 = max(0, cy - radius)
        x2 = min(w, cx + radius)
        y2 = min(h, cy + radius)
        crop = img.crop((x1, y1, x2, y2))
        return pil_to_b64(crop)


def draw_red_ring_b64(image_path: str, x: float, y: float) -> str:
    with Image.open(image_path) as img:
        img = img.convert("RGB").copy()
        w, h = img.size
        cx, cy = int(x * w), int(y * h)
        radius = max(15, min(100, w // 50))
        draw = ImageDraw.Draw(img)
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            outline="red",
            width=3,
        )
        dot_r = 4
        draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill="red")
        return pil_to_b64(img)
