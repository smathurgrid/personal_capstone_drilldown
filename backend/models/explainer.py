"""Explainer vision API request models."""

from typing import Literal, Optional

from pydantic import BaseModel, field_validator

from backend.shared.drill_mode import normalize_drill_mode
from backend.shared.grounding_defaults import default_grounding_mode

DrillMode = Literal["inside", "pov"]


class PageRequest(BaseModel):
    query: Optional[str] = None
    parentId: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    customTopic: Optional[str] = None
    visionModel: Optional[str] = "qwen3.5"
    groundingMode: Optional[str] = None
    drillMode: DrillMode = "inside"
    cacheBust: Optional[str] = None
    kbId: Optional[str] = None

    @field_validator("drillMode", mode="before")
    @classmethod
    def validate_drill_mode(cls, value: object) -> str:
        return normalize_drill_mode(value if value is not None else None)

    @field_validator("groundingMode", mode="before")
    @classmethod
    def validate_grounding_mode(cls, value: object) -> str:
        if value is None or not str(value).strip():
            return default_grounding_mode()
        return str(value).strip().lower()


class AnalyzeRequest(BaseModel):
    pageId: str
    visionModel: Optional[str] = "qwen3.5"
    scanMode: Optional[str] = "global"
    depth: Optional[int] = None


class ConfirmDrillRequest(BaseModel):
    pageId: str
    drillTopic: Optional[str] = None
