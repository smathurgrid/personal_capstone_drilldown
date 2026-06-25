"""Explainer image generation via Ollama or mock provider."""

import base64
import io
import logging
import textwrap
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from backend.core.protocols import ImageGenerator  # noqa: F401 — used in type hints
from backend.shared.config import settings
from backend.shared.llm_client import get_llm_client

logger = logging.getLogger(__name__)


class OllamaImageGenerator:
    def __init__(self) -> None:
        self.base_url = f"{settings.OLLAMA_BASE}/api/generate"
        self.model = settings.IMAGE_MODEL

    async def generate(
        self, prompt: str, local_crop_b64: str | None, global_b64: str | None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        images = [img for img in (local_crop_b64, global_b64) if img]
        if images:
            payload["images"] = images

        resp = requests.post(self.base_url, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        if data.get("image"):
            return {"image_b64": data["image"]}
        if data.get("images"):
            return {"image_b64": data["images"][0]}
        
        # Robust fallback for Ollama text-to-image experimental API (where base64 is in the response field)
        response_val = data.get("response", "")
        if response_val and isinstance(response_val, str):
            stripped = response_val.strip()
            if len(stripped) > 5000 and " " not in stripped and "\n" not in stripped:
                return {"image_b64": stripped}

        preview = str(data.get("response", ""))[:300]
        raise ValueError(f"Model returned no image. Response preview: {preview}")


class MockImageGenerator:
    async def generate(
        self, prompt: str, local_crop_b64: str | None, global_b64: str | None
    ) -> dict[str, Any]:
        del global_b64
        if local_crop_b64:
            img = Image.open(io.BytesIO(base64.b64decode(local_crop_b64))).convert("RGB")
        else:
            img = Image.new("RGB", (512, 512), color=(235, 238, 232))
        img = img.resize((512, 512), Image.LANCZOS)
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        text = textwrap.shorten(prompt.replace("\n", " "), width=80, placeholder="...")
        draw.rectangle([(0, 472), (512, 512)], fill=(0, 0, 0, 180))
        draw.text((8, 476), text, fill=(255, 255, 255), font=font)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return {"image_b64": base64.b64encode(buf.getvalue()).decode()}


class PollinationsImageGenerator:
    async def generate(
        self, prompt: str, local_crop_b64: str | None, global_b64: str | None
    ) -> dict[str, Any]:
        import urllib.parse
        del local_crop_b64, global_b64
        
        # Sanitize prompt of slashes to prevent CDN/CDN path resolution 404 errors
        safe_prompt = prompt.replace("/", " ").replace("\\", " ")
        # Truncate prompt to 1500 chars to avoid URL length-limit errors
        if len(safe_prompt) > 1500:
            safe_prompt = safe_prompt[:1500].rsplit(",", 1)[0]
            
        encoded = urllib.parse.quote(safe_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?model=flux&width=1024&height=1024&nologo=true"
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        b64_str = base64.b64encode(resp.content).decode("utf-8")
        return {"image_b64": b64_str}


class FalImageGenerator:
    async def generate(
        self, prompt: str, local_crop_b64: str | None, global_b64: str | None
    ) -> dict[str, Any]:
        del local_crop_b64, global_b64
        
        url = "https://fal.run/fal-ai/flux-lora"
        headers = {
            "Authorization": f"Key {settings.FAL_KEY}",
            "Content-Type": "application/json"
        }
        
        final_prompt = prompt
        loras = []
        if "first-person" in prompt or "POV" in prompt or "point-of-view" in prompt:
            if "PVSHTS_PPLSNSM" not in prompt:
                final_prompt = f"PVSHTS_PPLSNSM first person POV shot of {prompt}"
            
            loras.append({
                "path": settings.POV_LORA_PATH,
                "scale": 0.9
            })
            
        payload = {
            "prompt": final_prompt,
            "image_size": "square_hd",
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
            "sync_mode": True
        }
        if loras:
            payload["loras"] = loras
            
        resp = requests.post(url, headers=headers, json=payload, timeout=180)
        resp.raise_for_status()
        data = resp.json()
        
        images = data.get("images", [])
        if not images:
            raise ValueError(f"Fal.ai returned no images. Response: {data}")
            
        image_url = images[0]["url"]
        
        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
        b64_str = base64.b64encode(img_resp.content).decode("utf-8")
        return {"image_b64": b64_str}


class HuggingFaceImageGenerator:
    async def generate(
        self, prompt: str, local_crop_b64: str | None, global_b64: str | None
    ) -> dict[str, Any]:
        del local_crop_b64, global_b64
        
        # Use Hugging Face's active 2026 Router endpoint and the free, ultra-fast FLUX.1-schnell model
        url = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
        headers = {
            "Authorization": f"Bearer {settings.HF_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # Sanitize prompt of slashes to prevent HTTP/CDN formatting issues
        safe_prompt = prompt.replace("/", " ").replace("\\", " ")
        
        payload = {
            "inputs": safe_prompt,
        }
        
        resp = requests.post(url, headers=headers, json=payload, timeout=180)
        resp.raise_for_status()
        
        b64_str = base64.b64encode(resp.content).decode("utf-8")
        return {"image_b64": b64_str}


async def generate_topic_image(
    topic: str,
    *,
    image_generator: ImageGenerator,
) -> dict[str, str]:
    prompt_for_vlm = f"""You are an educational illustrator. A user wants to explore: "{topic}"

Create a detailed image generation prompt for the FIRST overview illustration.
Style: clean technical illustration, soft watercolor or muted palette.
CRITICAL: Do NOT include ANY text, labels, or words in the image.

Respond with ONLY the image generation prompt, nothing else."""

    if settings.MODEL_PROVIDER == "mock":
        image_prompt = f"Educational illustration of {topic}"
        result = await image_generator.generate(image_prompt, None, None)
    else:
        llm = get_llm_client()
        image_prompt = llm.chat_completion(
            settings.VISION_MODEL,
            prompt_for_vlm,
            temperature=0.3,
            timeout=120,
        ).strip()
        result = await image_generator.generate(image_prompt, None, None)

    return {"image_b64": result["image_b64"], "image_prompt": image_prompt}


async def generate_from_text(
    topic: str,
    *,
    image_generator: ImageGenerator | None = None,
) -> dict[str, str]:
    if image_generator is None:
        from backend.core.factory import get_service_factory

        image_generator = get_service_factory().create_image_generator()
    return await generate_topic_image(topic, image_generator=image_generator)
