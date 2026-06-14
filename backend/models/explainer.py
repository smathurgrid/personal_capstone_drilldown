"""Explainer vision API request models."""

from typing import Optional

from pydantic import BaseModel


class PageRequest(BaseModel):
    query: Optional[str] = None
    parentId: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    customTopic: Optional[str] = None
    visionModel: Optional[str] = "qwen3.5"
    groundingMode: Optional[str] = None


class AnalyzeRequest(BaseModel):
    pageId: str
    visionModel: Optional[str] = "qwen3.5"
    scanMode: Optional[str] = "global"


class ConfirmDrillRequest(BaseModel):
    pageId: str
    drillTopic: Optional[str] = None
