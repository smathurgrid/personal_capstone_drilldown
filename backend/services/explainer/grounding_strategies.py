"""Grounding strategy implementations (OCP)."""

import asyncio
from dataclasses import dataclass
from typing import Protocol

from backend.repositories.page_repository import PageRepository
from backend.services.explainer.image_compositor import ImageCompositor
from backend.services.explainer.segmentation_service import SAM2Service


@dataclass
class GroundingResult:
    segment_path: str | None
    marked_path: str | None
    confidence: float | None


class GroundingStrategy(Protocol):
    async def isolate(
        self,
        parent_path: str,
        x: float,
        y: float,
        page_id: str,
        page_store: PageRepository,
    ) -> GroundingResult: ...


class Sam2GroundingStrategy:
    async def isolate(
        self,
        parent_path: str,
        x: float,
        y: float,
        page_id: str,
        page_store: PageRepository,
    ) -> GroundingResult:
        if SAM2Service is None:
            return GroundingResult(segment_path=None, marked_path=None, confidence=None)

        segment_file = page_store.segment_image_path(page_id)
        loop = asyncio.get_event_loop()
        try:
            sam_info = await loop.run_in_executor(
                None,
                lambda: SAM2Service.segment_object(parent_path, x, y, str(segment_file)),
            )
            return GroundingResult(
                segment_path=str(segment_file),
                marked_path=None,
                confidence=sam_info["confidence"],
            )
        except Exception as exc:
            print(f"SAM2 failed: {exc}")
            return GroundingResult(segment_path=None, marked_path=None, confidence=None)


class RedRingGroundingStrategy:
    async def isolate(
        self,
        parent_path: str,
        x: float,
        y: float,
        page_id: str,
        page_store: PageRepository,
    ) -> GroundingResult:
        marked_file = page_store.marked_image_path(page_id)
        ImageCompositor.draw_red_ring(parent_path, x, y, str(marked_file))
        return GroundingResult(segment_path=None, marked_path=str(marked_file), confidence=None)


def get_grounding_strategy(mode: str) -> GroundingStrategy:
    if mode == "sam2":
        return Sam2GroundingStrategy()
    return RedRingGroundingStrategy()
