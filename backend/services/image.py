from abc import ABC, abstractmethod
from typing import Dict, Any
import base64
import io
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap
from ..config import settings

class BaseImageService(ABC):
    @abstractmethod
    async def generate(self, prompt: str, local_crop_b64: str, global_b64: str) -> Dict[str, Any]:
        pass

class OllamaImageService(BaseImageService):
    def __init__(self):
        self.base_url = f"{settings.OLLAMA_BASE}/api/generate"
        self.model = settings.IMAGE_MODEL

    async def generate(self, prompt: str, local_crop_b64: str, global_b64: str) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [local_crop_b64, global_b64],
            "stream": False,
        }
        resp = requests.post(self.base_url, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        if "image" in data and data["image"]:
            return {"image_b64": data["image"]}
        elif "images" in data and data["images"]:
            return {"image_b64": data["images"][0]}
        else:
            raise ValueError("Model returned no image")

class MockImageService(BaseImageService):
    async def generate(self, prompt: str, local_crop_b64: str, global_b64: str) -> Dict[str, Any]:
        import base64, io
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
        import textwrap
        img = base64.b64decode(local_crop_b64)
        img = Image.open(io.BytesIO(img)).convert("RGB")
        img = img.resize((512, 512), Image.LANCZOS)
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        text = textwrap.shorten(prompt.replace('\n', ' '), width=80, placeholder="...")
        draw.rectangle([(0, 472), (512, 512)], fill=(0, 0, 0, 180))
        draw.text((8, 476), text, fill=(255, 255, 255), font=font)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return {"image_b64": b64}
