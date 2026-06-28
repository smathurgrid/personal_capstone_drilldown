"""Explainer generation request handlers."""

import requests

from backend.core.protocols import ImageGenerator
from backend.services.explainer.image_generator import generate_from_text
from backend.shared.config import settings
from backend.shared.errors import AppError


class _SourceAddressAdapter(requests.adapters.HTTPAdapter):
    """Binds outgoing connections to a specific local IP so LAN traffic leaves via
    the LAN interface instead of a corporate VPN tunnel."""

    def __init__(self, source_ip: str, **kwargs) -> None:
        self._source_ip = source_ip
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        from urllib3.poolmanager import PoolManager

        pool_kwargs["source_address"] = (self._source_ip, 0)
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize, block=block, **pool_kwargs
        )


def _lan_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False  # ignore HTTP_PROXY/HTTPS_PROXY env vars
    if settings.BIND_LAN_IP:
        adapter = _SourceAddressAdapter(settings.BIND_LAN_IP)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
    return session


def _endpoint_reachable(base: str) -> bool:
    try:
        # Reach LAN worker Macs DIRECTLY: no proxy, and (if BIND_LAN_IP set) out the
        # LAN interface so a VPN tunnel doesn't black-hole the connection.
        resp = _lan_session().get(
            f"{base.rstrip('/')}/api/tags",
            timeout=5,
            headers={"ngrok-skip-browser-warning": "true"},
        )
        return resp.ok
    except requests.RequestException:
        return False


def get_generation_module_status() -> dict:
    if settings.MODEL_PROVIDER == "mock":
        vlm_ok = True
        image_workers: dict[str, bool] = {}
        main_image_ok = True
    else:
        vlm_ok = _endpoint_reachable(settings.VLM_OLLAMA_BASE)
        main_image_ok = _endpoint_reachable(settings.MAIN_IMAGE_BASE)
        # One reachability probe per worker Mac — this is the multi-Mac check.
        image_workers = {b: _endpoint_reachable(b) for b in settings.IMAGE_OLLAMA_BASES}
    workers_ok = settings.MODEL_PROVIDER == "mock" or any(image_workers.values())
    return {
        "module": "explainer-generation",
        "stage": settings.STAGE,
        "ready": (vlm_ok and workers_ok) or settings.MODEL_PROVIDER == "mock",
        "source": "explainer-generation",
        "provider": settings.MODEL_PROVIDER,
        "checks": {
            "vlm": vlm_ok,
            "vlm_base": settings.VLM_OLLAMA_BASE,
            "main_image_base": settings.MAIN_IMAGE_BASE,
            "main_image_reachable": main_image_ok,
            "image_backend": settings.IMAGE_BACKEND,
            "image_workers": image_workers,
            "workers_reachable": f"{sum(image_workers.values())}/{len(image_workers)}",
            "image_model": settings.IMAGE_MODEL,
            "vision_model": settings.VISION_MODEL,
            "llm_provider": settings.LLM_PROVIDER,
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
