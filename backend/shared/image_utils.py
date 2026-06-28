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


def crop_bbox_b64(
    image_bytes: bytes,
    bbox: tuple[float, float, float, float],
    pad_ratio: float = 0.08,
) -> str:
    """Crop a normalized bbox [x0,y0,x1,y1] from image bytes; returns base64 PNG.

    Used at dispatch time to give Flux a visual anchor for each hotspot without any
    extra VLM call (Approach 2: the bbox already came from the single prediction pass).
    A small pad is added so the crop keeps a little surrounding context.
    """
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        w, h = img.size
        x0, y0, x1, y1 = bbox
        # Normalize ordering and clamp to [0,1].
        x0, x1 = sorted((max(0.0, min(1.0, x0)), max(0.0, min(1.0, x1))))
        y0, y1 = sorted((max(0.0, min(1.0, y0)), max(0.0, min(1.0, y1))))
        pad_x = (x1 - x0) * pad_ratio
        pad_y = (y1 - y0) * pad_ratio
        px0 = int(max(0.0, x0 - pad_x) * w)
        py0 = int(max(0.0, y0 - pad_y) * h)
        px1 = int(min(1.0, x1 + pad_x) * w)
        py1 = int(min(1.0, y1 + pad_y) * h)
        # Guard against a degenerate (zero-area) box.
        if px1 - px0 < 8:
            px0, px1 = max(0, px0 - 8), min(w, px1 + 8)
        if py1 - py0 < 8:
            py0, py1 = max(0, py0 - 8), min(h, py1 + 8)
        crop = img.crop((px0, py0, px1, py1))
        return pil_to_b64(crop)


def prepare_drill_surfaces(
    image_bytes: bytes,
    x_px: int,
    y_px: int,
    radius_px: int = 80,
) -> tuple[str, str, int, int]:
    """Draw red reticle on full image and crop local region (pixel coords)."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        w, h = img.size
        cx = max(0, min(w - 1, int(x_px)))
        cy = max(0, min(h - 1, int(y_px)))
        radius = max(8, int(radius_px))

        marked = img.copy()
        ring_r = max(15, min(100, w // 50))
        draw = ImageDraw.Draw(marked)
        draw.ellipse(
            [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
            outline="red",
            width=3,
        )
        dot_r = 4
        draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill="red")

        x1 = max(0, cx - radius)
        y1 = max(0, cy - radius)
        x2 = min(w, cx + radius)
        y2 = min(h, cy + radius)
        crop = img.crop((x1, y1, x2, y2))
        return pil_to_b64(marked), pil_to_b64(crop), w, h


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
