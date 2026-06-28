"""Image compositor — ported from branch_rohith."""

from PIL import Image, ImageDraw, ImageEnhance
import os


class ImageCompositor:
    @staticmethod
    def draw_spotlight(
        image_path: str, x: float, y: float, output_path: str, radius: int = 150, brightness: float = 0.2
    ):
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Source image not found: {image_path}")
        with Image.open(image_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            width, height = img.size
            cx, cy = int(x * width), int(y * height)
            enhancer = ImageEnhance.Brightness(img)
            dimmed = enhancer.enhance(brightness)
            mask = Image.new("L", (width, height), 0)
            draw = ImageDraw.Draw(mask)
            for r in range(radius, 0, -1):
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
            result = Image.composite(img, dimmed, mask)
            result.save(output_path, "PNG")
        return output_path

    @staticmethod
    def draw_red_ring(image_path: str, x: float, y: float, output_path: str, thickness: int = 3):
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Source image not found: {image_path}")
        with Image.open(image_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            width, height = img.size
            cx, cy = int(x * width), int(y * height)
            radius = max(15, min(100, width // 50))
            draw = ImageDraw.Draw(img)
            draw.ellipse(
                [cx - radius, cy - radius, cx + radius, cy + radius],
                outline="red",
                width=thickness,
            )
            dot_r = thickness * 2
            draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill="red")
            img.save(output_path, "PNG")
        return output_path

    @staticmethod
    def draw_crosshairs(image_path: str, x: float, y: float, output_path: str, color="red", thickness: int = 2):
        with Image.open(image_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            width, height = img.size
            cx, cy = int(x * width), int(y * height)
            draw = ImageDraw.Draw(img)
            draw.line([0, cy, width, cy], fill=color, width=thickness)
            draw.line([cx, 0, cx, height], fill=color, width=thickness)
            img.save(output_path, "PNG")
        return output_path

    @staticmethod
    def draw_radial_glow(image_path: str, x: float, y: float, output_path: str, radius: int = 80):
        with Image.open(image_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            width, height = img.size
            cx, cy = int(x * width), int(y * height)
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            for r in range(radius, 0, -5):
                alpha = int(180 * (1 - r / radius))
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 0, 0, alpha))
            base = img.convert("RGBA")
            result = Image.alpha_composite(base, overlay).convert("RGB")
            result.save(output_path, "PNG")
        return output_path
