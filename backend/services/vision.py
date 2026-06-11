from abc import ABC, abstractmethod
from typing import Dict, Any
import base64
import io
import requests
import logging
from PIL import Image, ImageDraw
from ..config import settings

logger = logging.getLogger(__name__)

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
        logger.info(f"Image loaded: size={original.size}, mode={original.mode}")
        
        # Marked image
        marked = original.copy()
        draw = ImageDraw.Draw(marked)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline="red", width=6)
        draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill="red")
        logger.info(f"Created marked image with red circle at ({x}, {y}), radius={radius}")
        
        # Crop
        x1 = max(0, x - radius)
        y1 = max(0, y - radius)
        x2 = min(original.width, x + radius)
        y2 = min(original.height, y + radius)
        local_crop = original.crop((x1, y1, x2, y2))
        logger.info(f"Cropped local region: box=({x1}, {y1}, {x2}, {y2}), size={local_crop.size}")
        
        # Encode to base64
        def pil_to_b64(img: Image.Image) -> str:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64_str = base64.b64encode(buf.getvalue()).decode()
            logger.debug(f"Encoded image to base64: {len(b64_str)} chars, ~{len(buf.getvalue())} bytes")
            return b64_str
            
        global_b64 = pil_to_b64(marked)
        local_b64 = pil_to_b64(local_crop)
        logger.info(f"Both image crops encoded. Sending to Ollama vision model...")
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
        # Place images inside the message object (Ollama's /api/chat requires this format for vision models)
        images_list = [img for img in (global_b64, local_b64) if img]
        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": prompt,
                "images": images_list,
            }],
            "stream": False,
        }

        logger.info(f"Vision request: model={self.model}, images={len(images_list)}, prompt_len={len(prompt)}")
        logger.info(f"Image payload: global_b64_len={len(images_list[0]) if len(images_list) > 0 else 0}, local_b64_len={len(images_list[1]) if len(images_list) > 1 else 0}")
        resp = requests.post(self.base_url, json=payload, timeout=120)
        logger.info(f"Vision response status: {resp.status_code}")
        if resp.status_code != 200:
            logger.error(f"Vision error response: {resp.text[:500]}")
        resp.raise_for_status()
        data = resp.json()

        # Normalize response content across possible Ollama response shapes
        result = None
        if isinstance(data, dict):
            if "message" in data and isinstance(data["message"], dict) and "content" in data["message"]:
                result = data["message"]["content"]
            elif "choices" in data and data["choices"]:
                # common chat-like response shape
                first = data["choices"][0]
                if isinstance(first, dict) and "message" in first and "content" in first.get("message", {}):
                    result = first["message"]["content"]
            elif "response" in data:
                result = data["response"]

        if not result:
            preview = str(data)[:500]
            raise ValueError(f"Unable to parse model response. Preview: {preview}")

        logger.debug(f"Raw response from vision model (first 300 chars): {result[:300]}")

        # Parse the response to extract ANALYSIS and IMAGE PROMPT sections
        analysis_text = ""
        image_prompt = ""
        
        # Expected format from the prompt:
        # ANALYSIS:
        # <analysis text>
        # IMAGE PROMPT:
        # <image prompt text>
        
        if "ANALYSIS:" in result and "IMAGE PROMPT:" in result:
            # Split by both markers
            analysis_part = result.split("ANALYSIS:")[1].split("IMAGE PROMPT:")[0].strip()
            prompt_part = result.split("IMAGE PROMPT:")[1].strip()
            analysis_text = analysis_part
            image_prompt = prompt_part
        elif "IMAGE PROMPT:" in result:
            # Only IMAGE PROMPT found, extract it
            image_prompt = result.split("IMAGE PROMPT:")[1].strip()
            # Try to find ANALYSIS in the part before IMAGE PROMPT
            if "ANALYSIS:" in result:
                analysis_text = result.split("ANALYSIS:")[1].split("IMAGE PROMPT:")[0].strip()
            else:
                analysis_text = "Region analyzed successfully."
        elif "ANALYSIS:" in result:
            # Only ANALYSIS found
            analysis_text = result.split("ANALYSIS:")[1].strip()
            # Use analysis as fallback for image prompt
            image_prompt = analysis_text
        else:
            # Neither marker found - the model might have changed its format
            logger.warning(f"Response format unexpected. No ANALYSIS: or IMAGE PROMPT: markers found.")
            logger.warning(f"Full response (first 600 chars): {result[:600]}")
            # Fallback: try to split the response intelligently
            # Look for paragraphs separated by double newlines
            paragraphs = result.split('\n\n')
            if len(paragraphs) >= 2:
                # Assume first paragraph(s) are analysis, last is prompt
                analysis_text = '\n\n'.join(paragraphs[:-1]).strip()
                image_prompt = paragraphs[-1].strip()
            else:
                # Single paragraph - split roughly in middle
                halfway = len(result) // 2
                analysis_text = result[:halfway].strip()
                image_prompt = result[halfway:].strip()
            logger.warning(f"Using fallback split: analysis_len={len(analysis_text)}, prompt_len={len(image_prompt)}")
        
        logger.info(f"Vision parsing: analysis_len={len(analysis_text)}, prompt_len={len(image_prompt)}")
        logger.debug(f"Analysis (first 200): {analysis_text[:200]}")
        logger.debug(f"Image Prompt (first 200): {image_prompt[:200]}")
        
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
        analysis_text = f"The selected region at ({x},{y}) appears visually consistent with a centered feature. It likely contains textures and small-scale details worth zooming into."
        image_prompt = f"Photorealistic close-up of the region centered at ({x},{y}) from the provided scene."
        return {
            "analysis": analysis_text,
            "image_prompt": image_prompt,
            "local_crop_b64": local_crop_b64,
            "marked_image_b64": global_b64,
        }
