"""Ollama reachability checks for vision and generation."""

from __future__ import annotations

import requests

from backend.shared.config import settings
from backend.shared.errors import AppError

_OLLAMA_HELP = "Start Ollama in another terminal: ollama serve"


def ollama_reachable(timeout: float = 2.0) -> bool:
    """True when Ollama HTTP API responds (or mock mode is enabled)."""
    if settings.MODEL_PROVIDER == "mock":
        return True
    try:
        resp = requests.get(
            f"{settings.OLLAMA_BASE.rstrip('/')}/api/tags",
            timeout=timeout,
        )
        return resp.ok
    except requests.RequestException:
        return False


def require_ollama(message: str | None = None) -> None:
    """Raise AppError when Ollama is required but not reachable."""
    if settings.MODEL_PROVIDER == "mock":
        return
    if ollama_reachable():
        return
    raise AppError(
        "OLLAMA_UNAVAILABLE",
        message or f"Ollama is not running at {settings.OLLAMA_BASE}. {_OLLAMA_HELP}",
        status_code=503,
        detail={"ollama_base": settings.OLLAMA_BASE, "hint": _OLLAMA_HELP},
    )


def ollama_connection_app_error(exc: BaseException) -> AppError:
    """Map requests connection failures to a stable API error."""
    return AppError(
        "OLLAMA_UNAVAILABLE",
        f"Cannot reach Ollama at {settings.OLLAMA_BASE}. {_OLLAMA_HELP}",
        status_code=503,
        detail={"ollama_base": settings.OLLAMA_BASE, "reason": str(exc)},
    )
