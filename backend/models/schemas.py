"""Shared API response contracts."""

from typing import Any

from pydantic import BaseModel, Field


class HealthModuleStatus(BaseModel):
    status: str = "ok"
    module: str
    stage: int
    ready: bool
    source: str
    checks: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None
    provider: str | None = None


class GlobalHealthResponse(BaseModel):
    status: str
    stage: int
    modules: dict[str, HealthModuleStatus]
