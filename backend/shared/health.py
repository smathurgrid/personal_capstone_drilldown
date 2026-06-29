"""Shared health-check route registration for module controllers."""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter


def register_module_health(router: APIRouter, status_fn: Callable[[], dict[str, Any]]) -> None:
    """Mount GET / and GET /health returning {"status": "ok", **status_fn()}."""

    async def health() -> dict[str, Any]:
        return {"status": "ok", **status_fn()}

    router.add_api_route("/", health, methods=["GET"])
    router.add_api_route("/health", health, methods=["GET"])
