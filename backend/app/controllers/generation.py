"""Explainer generation request handlers."""

import requests

from backend.core.protocols import ImageGenerator
from backend.services.explainer.image_generator import generate_from_text
from backend.shared.config import settings
from backend.shared.errors import AppError


def _ollama_reachable() -> bool:
    if settings.MODEL_PROVIDER == "mock":
        return True
    try:
        resp = requests.get(f"{settings.OLLAMA_BASE}/api/tags", timeout=2)
        return resp.ok
    except requests.RequestException:
        return False


def _image_model_available() -> bool:
    if settings.MODEL_PROVIDER == "mock":
        return True
    try:
        resp = requests.get(f"{settings.OLLAMA_BASE}/api/tags", timeout=2)
        if not resp.ok:
            return False
        installed = {m.get("name", "") for m in resp.json().get("models", [])}
        target = settings.IMAGE_MODEL
        base = target.split(":")[0]
        return target in installed or any(n.startswith(base) for n in installed)
    except requests.RequestException:
        return False


def get_generation_module_status() -> dict:
    ollama_ok = _ollama_reachable()
    image_model_ok = _image_model_available()
    using_mock = settings.MODEL_PROVIDER == "mock"
    return {
        "module": "explainer-generation",
        "stage": settings.STAGE,
        "ready": (ollama_ok and image_model_ok) or using_mock,
        "source": "explainer-generation",
        "provider": settings.MODEL_PROVIDER,
        "checks": {
            "ollama": ollama_ok,
            "image_model_installed": image_model_ok,
            "image_model": settings.IMAGE_MODEL,
            "vision_model": settings.VISION_MODEL,
            "ollama_base": settings.OLLAMA_BASE,
            "llm_provider": settings.LLM_PROVIDER,
            "litellm_proxy": settings.LITELLM_PROXY_BASE if settings.LLM_PROVIDER == "litellm" else None,
            "mock_placeholder_images": using_mock,
        },
    }


async def handle_generate(body: dict, image_generator: ImageGenerator):
    prompt = body.get("prompt", "")
    local_crop_b64 = body.get("local_crop_b64")
    global_b64 = body.get("global_b64")
    if not local_crop_b64 and settings.MODEL_PROVIDER != "mock":
        raise AppError("VALIDATION_ERROR", "local_crop_b64 required", status_code=400)
    return await image_generator.generate(prompt, local_crop_b64, global_b64)


async def handle_generate_from_text(body: dict, image_generator: ImageGenerator):
    topic = str(body.get("topic", "")).strip()
    if not topic:
        raise AppError("VALIDATION_ERROR", "topic required", status_code=400)
    return await generate_from_text(topic, image_generator=image_generator)
