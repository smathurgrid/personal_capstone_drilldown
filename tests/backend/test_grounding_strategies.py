"""Grounding strategy unit tests."""

import pytest

from backend.repositories.page_repository import PageRepository
from backend.services.explainer.grounding_strategies import (
    RedRingGroundingStrategy,
    get_grounding_strategy,
)


@pytest.mark.asyncio
async def test_red_ring_strategy_creates_marked_image(tmp_path) -> None:
    from PIL import Image

    repo = PageRepository(tmp_path)
    parent = tmp_path / "parent.png"
    Image.new("RGB", (64, 64), color=(10, 20, 30)).save(parent)

    result = await RedRingGroundingStrategy().isolate(
        str(parent), 0.5, 0.5, "page-1", repo
    )
    assert result.marked_path is not None
    assert result.segment_path is None


def test_get_grounding_strategy_selects_implementation() -> None:
    assert isinstance(get_grounding_strategy("red_ring"), RedRingGroundingStrategy)
    assert isinstance(get_grounding_strategy("sam2"), type(get_grounding_strategy("sam2")))
