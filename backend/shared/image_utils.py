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


def compute_drill_crop_radius(
    width: int,
    height: int,
    *,
    radius_ratio: float = 0.05, # Tighter crop for higher focal magnification!
    min_radius: int = 50,       # Let it zoom tighter!
) -> int:
    """Scale-aware crop radius — 5% of shorter side, minimum 50px."""
    return max(min_radius, int(min(width, height) * radius_ratio))


def crop_norm_region(
    image_path: str,
    x: float,
    y: float,
    radius_ratio: float = 0.05, # Tighter crop for higher focal magnification!
    *,
    min_radius: int = 50,       # Let it zoom tighter!
) -> str:
    """Crop a square region around normalized (x,y); returns base64 PNG."""
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        w, h = img.size
        cx, cy = int(x * w), int(y * h)
        radius = compute_drill_crop_radius(w, h, radius_ratio=radius_ratio, min_radius=min_radius)
        x1 = max(0, cx - radius)
        y1 = max(0, cy - radius)
        x2 = min(w, cx + radius)
        y2 = min(h, cy + radius)
        
        # Ensure valid crop coordinates
        if x1 >= x2:
            x1 = max(0, cx - 40)
            x2 = min(w, cx + 40)
        if y1 >= y2:
            y1 = max(0, cy - 40)
            y2 = min(h, cy + 40)
        
        # Final validation
        x2 = max(x1 + 1, x2)
        y2 = max(y1 + 1, y2)
        
        crop = img.crop((x1, y1, x2, y2))
        return pil_to_b64(crop)


def prepare_wide_context_crop(
    image_bytes: bytes,
    x_px: int,
    y_px: int,
    frame_ratio: float = 0.4,
) -> str:
    """Wide context crop around click — scene context for POV VLM, not macro detail."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        w, h = img.size
        cx = max(0, min(w - 1, int(x_px)))
        cy = max(0, min(h - 1, int(y_px)))
        radius = max(64, int(min(w, h) * frame_ratio))

        x1 = max(0, cx - radius)
        y1 = max(0, cy - radius)
        x2 = min(w, cx + radius)
        y2 = min(h, cy + radius)

        if x1 >= x2:
            x1 = max(0, cx - 64)
            x2 = min(w, cx + 64)
        if y1 >= y2:
            y1 = max(0, cy - 64)
            y2 = min(h, cy + 64)

        x2 = max(x1 + 1, x2)
        y2 = max(y1 + 1, y2)

        crop = img.crop((x1, y1, x2, y2))
        return pil_to_b64(crop)


def prepare_drill_surfaces(
    image_bytes: bytes,
    x_px: int,
    y_px: int,
    radius_px: int | None = None,
) -> tuple[str, str, int, int]:
    """Draw red reticle on full image and crop local region (pixel coords)."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        w, h = img.size
        cx = max(0, min(w - 1, int(x_px)))
        cy = max(0, min(h - 1, int(y_px)))
        radius = radius_px if radius_px is not None else compute_drill_crop_radius(w, h)
        radius = max(8, int(radius))

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
        
        # Ensure valid crop coordinates
        if x1 >= x2:
            x1 = max(0, cx - 40)
            x2 = min(w, cx + 40)
        if y1 >= y2:
            y1 = max(0, cy - 40)
            y2 = min(h, cy + 40)
        
        # Final validation
        x2 = max(x1 + 1, x2)
        y2 = max(y1 + 1, y2)
        
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
