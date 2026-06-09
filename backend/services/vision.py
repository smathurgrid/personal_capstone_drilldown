from abc import ABC, abstractmethod
from typing import Dict, Any
import base64
import io
import requests
from PIL import Image, ImageDraw
from ..config import settings

class BaseVisionService(ABC):
    @abstractmethod
    async def analyze(self, image_bytes: bytes, x: int, y: int, radius: int) -> Dict[str, Any]:
        pass

class OllamaVisionService(BaseVisionService):
    def __init__(self):
        self.base_url = f"{settings.OLLAMA_BASE}/api/chat"
        self.model = settings.VISION_MODEL

    async def analyze(self, image_bytes: bytes, x: int, y: int, radius: int) -> Dict[str, Any]:
        # Convert bytes to PIL
        original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        # Marked image
        marked = original.copy()
        draw = ImageDraw.Draw(marked)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline="red", width=6)
        draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill="red")
        # Crop
        x1 = max(0, x - radius)
        y1 = max(0, y - radius)
        x2 = min(original.width, x + radius)
        y2 = min(original.height, y + radius)
        local_crop = original.crop((x1, y1, x2, y2))
        # Encode to base64
        def pil_to_b64(img: Image.Image) -> str:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()
        global_b64 = pil_to_b64(marked)
        local_b64 = pil_to_b64(local_crop)
        # Prompt (same as before)
        prompt = """You are analyzing an image for a recursive semantic drill-down visualization.
This is an EDUCATIONAL EXPLAINER tool — like an illustrated textbook or infographic.

You are given TWO images:
  Image 1 — FULL scene with a RED circle marking the region of interest (global context)
  Image 2 — A CLOSE-UP crop of exactly what is inside the red circle (local context)

Your task:
1. Use Image 1 to understand WHERE in the scene this region is.
2. Use Image 2 to understand WHAT is actually there in fine detail.
3. Describe what hidden internal structures, layers, components, or deeper details
   naturally exist inside this region — things a student would want to learn about.

Format your response EXACTLY like this:

ANALYSIS:
<2-3 sentences combining global + local understanding>

IMAGE PROMPT:
<A single paragraph describing an EDUCATIONAL ILLUSTRATION of what is inside this
 region. Style: clean technical illustration, cross-section cutaway views, soft
 watercolor or muted palette, architectural/scientific diagram style.
 NOT photorealistic — think textbook illustration or encyclopedia diagram.
 CRITICAL: Do NOT include ANY text, labels, titles, annotations, callout lines,
 or words in the image. The image must be PURELY visual with ZERO text or lettering
 of any kind. Describe only visual elements, structures, colors, and composition.>"""
        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": prompt,
                "images": [global_b64, local_b64],
            }],
            "stream": False,
        }
        resp = requests.post(self.base_url, json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()["message"]["content"]
        analysis_text = result
        image_prompt = result
        if "IMAGE PROMPT:" in result:
            parts = result.split("IMAGE PROMPT:")
            image_prompt = parts[-1].strip()
            if "ANALYSIS:" in parts[0]:
                analysis_text = parts[0].split("ANALYSIS:")[-1].strip()
        return {
            "analysis": analysis_text,
            "image_prompt": image_prompt,
            "local_crop_b64": local_b64,
            "marked_image_b64": global_b64,
        }

# Mock service for deterministic local dev
class MockVisionService(BaseVisionService):
    async def analyze(self, image_bytes: bytes, x: int, y: int, radius: int) -> Dict[str, Any]:
        import textwrap
        from PIL import Image, ImageDraw, ImageFont
        import base64, io
        original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        marked = original.copy()
        draw = ImageDraw.Draw(marked)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline="red", width=6)
        draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill="red")
        x1 = max(0, x - radius)
        y1 = max(0, y - radius)
        x2 = min(original.width, x + radius)
        y2 = min(original.height, y + radius)
        local_crop = original.crop((x1, y1, x2, y2))
        def pil_to_b64(img: Image.Image) -> str:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()
        global_b64 = pil_to_b64(marked)
        local_b64 = pil_to_b64(local_crop)
        analysis_text = f"ANALYSIS:\nThe selected region at ({x},{y}) appears visually consistent with a centered feature. It likely contains textures and small-scale details worth zooming into."
        image_prompt = f"IMAGE PROMPT:\nPhotorealistic close-up of the region centered at ({x},{y}) from the provided scene."
        return {
            "analysis": analysis_text,
            "image_prompt": image_prompt,
            "local_crop_b64": local_b64,
            "marked_image_b64": global_b64,
        }
