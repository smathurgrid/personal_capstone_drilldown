"""Explainer image generation via Ollama or mock provider."""

import asyncio
import base64
import io
import logging
import textwrap
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from backend.core.protocols import ImageGenerator  # noqa: F401 — used in type hints
from backend.shared.config import settings
from backend.shared.errors import AppError
from backend.shared.llm_client import get_llm_client
from backend.shared.ollama_health import ollama_connection_app_error

logger = logging.getLogger(__name__)


async def ollama_generate_image(
    prompt: str,
    *,
    base_url: str,
    model: str,
    images: list[str] | None = None,
    timeout: int | None = None,
) -> str:
    """POST one image job to a SPECIFIC Ollama endpoint (async, for the worker pool).

    Reaches LAN/ngrok workers directly: ignores proxy env (trust_env=False), can bind
    to a LAN source IP (BIND_LAN_IP) to bypass a VPN tunnel, and sends the ngrok
    skip-warning header. Self-contained so it doesn't change the existing generator.
    """
    import httpx

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": settings.IMAGE_KEEP_ALIVE,
    }
    # Only pass the local crop (avoids the Flux "echo" loop), like the main generator.
    imgs = [i for i in (images or []) if i][:1]
    if imgs:
        payload["images"] = imgs
    url = f"{base_url.rstrip('/')}/api/generate"
    transport = (
        httpx.AsyncHTTPTransport(local_address=settings.BIND_LAN_IP)
        if settings.BIND_LAN_IP
        else None
    )
    async with httpx.AsyncClient(
        timeout=timeout or settings.IMAGE_GEN_TIMEOUT,
        trust_env=False,
        transport=transport,
        headers={"ngrok-skip-browser-warning": "true"},
    ) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    if data.get("image"):
        return data["image"]
    if data.get("images"):
        return data["images"][0]
    raise ValueError(f"Worker returned no image: {str(data.get('response',''))[:200]}")


def _ollama_generate(payload: dict[str, Any]) -> dict[str, Any]:
    # Pin the model in memory so spaced clicks don't pay the (large) reload cost.
    payload.setdefault("keep_alive", settings.IMAGE_KEEP_ALIVE)
    try:
        resp = requests.post(
            f"{settings.OLLAMA_BASE}/api/generate", json=payload, timeout=300
        )
    except requests.exceptions.ConnectionError as exc:
        raise ollama_connection_app_error(exc) from exc
    except requests.exceptions.Timeout as exc:
        raise AppError(
            "OLLAMA_TIMEOUT",
            "Ollama image generation timed out",
            status_code=504,
        ) from exc
    resp.raise_for_status()
    return resp.json()


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
        # Flux2 Klein supports reference-conditioned generation via `images` (img2img).
        # To prevent the "Echo" loop (where it keeps drawing the entire global scene),
        # we ONLY pass the local crop for 'inside' zooms. This forces Flux to zoom in
        # on the cropped texture/details and drill deeper, rather than redrawing the whole object.
        images: list[str] = []
        if local_crop_b64:
            images.append(local_crop_b64)
        else:
            if global_b64:
                images.append(global_b64)
                
        if images:
            payload["images"] = images[:1] # Pass only the most relevant image
            logger.info(
                "Flux reference images: %d (local=%s global=%s)",
                len(payload["images"]),
                bool(local_crop_b64),
                not bool(local_crop_b64),
            )

        data = await asyncio.to_thread(_ollama_generate, payload)
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
        image_prompt = await asyncio.to_thread(
            llm.chat_completion,
            settings.EXPLAINER_VISION_MODEL,
            prompt_for_vlm,
            temperature=0.3,
            timeout=120,
            num_predict=250,
        )
        image_prompt = image_prompt.strip()
        gen_payload = {
            "model": settings.IMAGE_MODEL,
            "prompt": image_prompt,
            "stream": False,
        }
        data = await asyncio.to_thread(_ollama_generate, gen_payload)
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
