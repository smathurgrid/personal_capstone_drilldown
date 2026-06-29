"""Object grounding for explainer drill-down using pluggable strategies."""

from backend.core.protocols import ExplainerPageStore
from backend.services.explainer.grounding_strategies import (
    GroundingResult,
    RedRingGroundingStrategy,
    get_grounding_strategy,
)


class GroundingService:
    def __init__(self, page_store: ExplainerPageStore) -> None:
        self._pages = page_store
        self._fallback = RedRingGroundingStrategy()

    async def isolate_region(
        self,
        parent_path: str,
        x: float,
        y: float,
        page_id: str,
        grounding_mode: str,
    ) -> GroundingResult:
        strategy = get_grounding_strategy(grounding_mode)
        result = await strategy.isolate(parent_path, x, y, page_id, self._pages)
        if result.segment_path or result.marked_path:
            return result
        return await self._fallback.isolate(parent_path, x, y, page_id, self._pages)
