"""Service contracts for dependency inversion (ISP + DIP)."""

from collections.abc import AsyncIterator
from typing import Any, Protocol


class ImageGenerator(Protocol):
    async def generate(
        self,
        prompt: str,
        local_crop_b64: str | None,
        global_b64: str | None,
    ) -> dict[str, Any]: ...


class ProductIdentification(Protocol):
    async def identify_item(
        self,
        original_image_path: str,
        composite_image_path: str,
        x: float,
        y: float,
    ) -> dict | None: ...


class ProductSearch(Protocol):
    def get_embedding(self, original_crop, composite_crop): ...

    async def hybrid_search(self, embedding, attributes: dict, limit: int = 50): ...


class DrillHistoryStore(Protocol):
    def append(self, node: dict) -> None: ...

    def list_all(self) -> list[dict]: ...

    def clear(self) -> None: ...


class ExplainerPageStore(Protocol):
    def compute_content_hash(self, key: str) -> str: ...

    def image_url(self, page_id: str) -> str: ...

    def initial_page_paths(self, query: str) -> tuple[str, Any]: ...

    def drill_hash_key(
        self,
        parent_id: str,
        x: float,
        y: float,
        vision_model: str,
        grounding_mode: str,
        coord_precision: int,
        custom_topic: str | None = None,
        *,
        include_custom_topic_in_hash: bool = False,
    ) -> str: ...

    def drill_page_paths(self, page_id: str) -> tuple[Any, Any]: ...

    def parent_image_path(self, parent_id: str) -> Any: ...

    def page_image_path(self, page_id: str) -> Any: ...

    def load_drill_cache(self, page_id: str) -> dict | None: ...

    def save_drill_metadata(self, metadata_path: Any, metadata: dict) -> None: ...

    @staticmethod
    def cleanup_temp_files(*paths: str | Any | None) -> None: ...


class ExplainerContextAnalysis(Protocol):
    async def analyze_page(self, image_path: str, model_key: str = "qwen3.5"): ...


class ExplainerPageWorkflow(Protocol):
    async def get_or_create_page(
        self,
        query: str | None = None,
        parent_id: str | None = None,
        x: float | None = None,
        y: float | None = None,
        vision_model: str = "qwen3.5",
        grounding_mode: str = "sam2",
        custom_topic: str | None = None,
    ): ...

    def stream_page(
        self,
        query: str | None = None,
        parent_id: str | None = None,
        x: float | None = None,
        y: float | None = None,
        vision_model: str = "qwen3.5",
        grounding_mode: str = "sam2",
        custom_topic: str | None = None,
    ) -> AsyncIterator[str]: ...
