"""Explainer image generation via Ollama or mock provider."""

import asyncio
import base64
import io
import logging
import textwrap
from typing import Any

import httpx
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from backend.core.protocols import ImageGenerator  # noqa: F401 — used in type hints
from backend.shared.config import settings
from backend.shared.llm_client import get_llm_client

logger = logging.getLogger(__name__)


def _extract_image_b64(data: dict[str, Any]) -> str:
    """Pull the base64 image out of an Ollama /api/generate response."""
    if data.get("image"):
        return data["image"]
    if data.get("images"):
        return data["images"][0]
    preview = str(data.get("response", ""))[:300]
    raise ValueError(f"Model returned no image. Response preview: {preview}")


async def ollama_generate_image(
    prompt: str,
    *,
    base_url: str,
    model: str,
    images: list[str] | None = None,
    timeout: int | None = None,
) -> str:
    """POST one image-generation job to a specific Ollama endpoint (async).

    Used by the worker pool to target individual Mac endpoints concurrently
    without blocking the event loop (unlike the legacy requests.post path).
    """
    payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
    if images:
        payload["images"] = images
    url = f"{base_url.rstrip('/')}/api/generate"
    # trust_env=False -> ignore HTTP_PROXY/HTTPS_PROXY env vars. Worker Macs are on
    # the LAN and must be reached DIRECTLY; a campus proxy would black-hole them.
    # local_address (BIND_LAN_IP) -> force the socket out the LAN interface so a
    # corporate VPN tunnel doesn't swallow the connection.
    transport = (
        httpx.AsyncHTTPTransport(local_address=settings.BIND_LAN_IP)
        if settings.BIND_LAN_IP
        else None
    )
    async with httpx.AsyncClient(
        timeout=timeout or settings.IMAGE_GEN_TIMEOUT,
        trust_env=False,
        transport=transport,
        headers={"ngrok-skip-browser-warning": "true"},  # bypass ngrok interstitial
    ) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return _extract_image_b64(resp.json())


class RemoteFluxImageGenerator:
    """Distributed inference client — sends prompts to the Mac 2 Flux worker.

    Conforms to the ImageGenerator protocol so it drops into the factory seam with no
    changes to call sites. Runs the blocking HTTP POST in a thread so it never stalls
    the event loop (the engine dispatches several of these back-to-back).
    """

    def __init__(self) -> None:
        self.base_url = f"{settings.REMOTE_FLUX_BASE.rstrip('/')}/generate"

    async def generate(
        self, prompt: str, local_crop_b64: str | None, global_b64: str | None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "prompt": prompt,
            "local_crop_b64": local_crop_b64,
            "global_b64": global_b64,
        }

        def _post() -> dict[str, Any]:
            resp = requests.post(self.base_url, json=payload, timeout=300)
            resp.raise_for_status()
            return resp.json()

        data = await asyncio.to_thread(_post)
        if not data.get("image_b64"):
            raise ValueError(f"Remote Flux worker returned no image_b64: {str(data)[:200]}")
        return {"image_b64": data["image_b64"]}


class OllamaImageGenerator:
    def __init__(self, base_url: str | None = None) -> None:
        base = base_url or settings.OLLAMA_BASE
        self.base_url = f"{base.rstrip('/')}/api/generate"
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
        gen_payload = {
            "model": settings.IMAGE_MODEL,
            "prompt": image_prompt,
            "stream": False,
        }
        r = requests.post(f"{settings.OLLAMA_BASE}/api/generate", json=gen_payload, timeout=300)
        r.raise_for_status()
        data = r.json()
        image_b64 = data.get("image") or (data.get("images") or [None])[0]
        if not image_b64:
            raise ValueError("Model returned no image for generate-from-text")
        result = {"image_b64": image_b64}

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
