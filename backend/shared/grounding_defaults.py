"""Grounding mode helpers — SAM2 when available, red ring fallback."""

from backend.services.explainer.segmentation_service import SAM2Service
from backend.shared.config import settings


def sam2_available() -> bool:
    return SAM2Service is not None


def default_grounding_mode() -> str:
    explicit = settings.DEFAULT_GROUNDING_MODE.strip().lower()
    if explicit in ("sam2", "red_ring"):
        return explicit
    return "sam2" if sam2_available() else "red_ring"
