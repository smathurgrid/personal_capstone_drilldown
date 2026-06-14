"""Explainer page workflow orchestration (topic, drill-down, streaming)."""

import json

from backend.core.protocols import (
    ExplainerPageStore,
    ExplainerPageWorkflow,
    ImageGenerator,
)
from backend.services.explainer.drill_context_resolver import DrillContextResolver
from backend.services.explainer.grounding_service import GroundingService
from backend.services.explainer.drill_workflow import (
    DrillWorkflow,
    build_result_metadata,
    extract_vision_fields,
)
from backend.services.explainer.stream_events import format_sse_event
from backend.shared.generation_bridge import generate_topic_image_to_file


class PageOrchestrator(ExplainerPageWorkflow):
    _DRILL_COORD_PRECISION = 4
    _DRILL_INCLUDE_CUSTOM_TOPIC_IN_HASH = True

    def __init__(
        self,
        page_store: ExplainerPageStore,
        grounding_service: GroundingService,
        drill_context_resolver: DrillContextResolver,
        image_generator: ImageGenerator,
    ) -> None:
        self._pages = page_store
        self._grounding = grounding_service
        self._drill_context = drill_context_resolver
        self._drill_workflow = DrillWorkflow(page_store, image_generator)
        self._image_generator = image_generator

    async def get_or_create_page(
        self,
        query: str | None = None,
        parent_id: str | None = None,
        x: float | None = None,
        y: float | None = None,
        vision_model: str = "qwen3.5",
        grounding_mode: str = "sam2",
        custom_topic: str | None = None,
    ):
        if query:
            page_id, output_path = self._pages.initial_page_paths(query)
            if output_path.exists():
                return {"id": page_id, "imageUrl": self._pages.image_url(page_id)}
            await generate_topic_image_to_file(
                query, output_path, image_generator=self._image_generator
            )
            return {"id": page_id, "imageUrl": self._pages.image_url(page_id)}

        if parent_id and x is not None and y is not None:
            return await self._run_drill(
                parent_id,
                x,
                y,
                vision_model,
                grounding_mode,
                custom_topic,
                coord_precision=self._DRILL_COORD_PRECISION,
                include_custom_topic_in_hash=self._DRILL_INCLUDE_CUSTOM_TOPIC_IN_HASH,
            )

        raise ValueError("Invalid parameters for page generation")

    async def stream_page(
        self,
        query: str | None = None,
        parent_id: str | None = None,
        x: float | None = None,
        y: float | None = None,
        vision_model: str = "qwen3.5",
        grounding_mode: str = "sam2",
        custom_topic: str | None = None,
    ):
        if query:
            yield format_sse_event("generating", {"message": "Generating initial image..."})
            page_id, output_path = self._pages.initial_page_paths(query)
            if not output_path.exists():
                await generate_topic_image_to_file(
                    query, output_path, image_generator=self._image_generator
                )
            yield format_sse_event(
                "complete", {"id": page_id, "imageUrl": self._pages.image_url(page_id)}
            )
            return

        if parent_id and x is not None and y is not None:
            async for event in self._stream_drill(
                parent_id,
                x,
                y,
                vision_model,
                grounding_mode,
                custom_topic,
            ):
                yield event
            return

        yield format_sse_event("error", {"message": "Invalid parameters for page generation"})

    async def _run_drill(
        self,
        parent_id: str,
        x: float,
        y: float,
        vision_model: str,
        grounding_mode: str,
        custom_topic: str | None,
        *,
        coord_precision: int,
        include_custom_topic_in_hash: bool,
    ):
        page_id, output_path, metadata_path, parent_path, grounding, vision_result, crop_path = (
            await self._prepare_drill(
                parent_id,
                x,
                y,
                vision_model,
                grounding_mode,
                custom_topic,
                coord_precision=coord_precision,
                include_custom_topic_in_hash=include_custom_topic_in_hash,
            )
        )

        if parent_path is None and isinstance(vision_result, dict) and vision_result.get("id"):
            return vision_result

        if vision_result.get("isComparison"):
            return {"id": page_id, "imageUrl": self._pages.image_url(parent_id), **vision_result}

        drill_topic, metadata, input_prompt, raw_json = extract_vision_fields(vision_result)
        result_metadata = build_result_metadata(
            drill_topic,
            metadata,
            input_prompt,
            raw_json,
            grounding.confidence,
            grounding_mode,
        )
        result_metadata.update(
            {
                "parentId": parent_id,
                "click": {"x": x, "y": y},
                "visionModel": vision_model,
                "groundingMode": grounding_mode,
                "depth": self._parent_depth(parent_id) + 1,
            }
        )

        return await self._drill_workflow.complete_drill(
            page_id,
            str(output_path),
            str(metadata_path),
            drill_topic,
            str(parent_path),
            x,
            y,
            grounding.segment_path,
            grounding.marked_path,
            crop_path,
            result_metadata,
        )

    async def _stream_drill(
        self,
        parent_id: str,
        x: float,
        y: float,
        vision_model: str,
        grounding_mode: str,
        custom_topic: str | None,
    ):
        page_id, output_path, metadata_path, parent_path, grounding, vision_result, crop_path = (
            await self._prepare_drill(
                parent_id,
                x,
                y,
                vision_model,
                grounding_mode,
                custom_topic,
                coord_precision=self._DRILL_COORD_PRECISION,
                include_custom_topic_in_hash=self._DRILL_INCLUDE_CUSTOM_TOPIC_IN_HASH,
                emit_sse=True,
            )
        )

        if isinstance(vision_result, dict) and vision_result.get("_cached"):
            yield format_sse_event("complete", vision_result["payload"])
            return

        if parent_path is None:
            yield format_sse_event("error", {"message": "Parent image not found."})
            return

        yield format_sse_event("grounding", {"message": "Isolating object..."})
        yield format_sse_event(
            "vision",
            {"message": "Analyzing component...", "samConfidence": grounding.confidence},
        )

        drill_topic, metadata, input_prompt, raw_json = extract_vision_fields(vision_result)
        result_metadata = build_result_metadata(
            drill_topic,
            metadata,
            input_prompt,
            raw_json,
            grounding.confidence,
            grounding_mode,
        )
        result_metadata.update(
            {
                "parentId": parent_id,
                "click": {"x": x, "y": y},
                "visionModel": vision_model,
                "groundingMode": grounding_mode,
                "depth": self._parent_depth(parent_id) + 1,
            }
        )

        yield format_sse_event(
            "generating",
            {
                "message": "Illustrating detail...",
                "metadata": metadata,
                "samConfidence": grounding.confidence,
                "rawJson": raw_json,
                "inputPrompt": input_prompt,
            },
        )
        yield format_sse_event("generating_image", {"message": "Rendering next layer..."})

        result = await self._drill_workflow.complete_drill(
            page_id,
            str(output_path),
            str(metadata_path),
            drill_topic,
            str(parent_path),
            x,
            y,
            grounding.segment_path,
            grounding.marked_path,
            crop_path,
            result_metadata,
        )
        yield format_sse_event("complete", result)

    async def _prepare_drill(
        self,
        parent_id: str,
        x: float,
        y: float,
        vision_model: str,
        grounding_mode: str,
        custom_topic: str | None,
        *,
        coord_precision: int,
        include_custom_topic_in_hash: bool,
        emit_sse: bool = False,
    ):
        hash_key = self._pages.drill_hash_key(
            parent_id,
            x,
            y,
            vision_model,
            grounding_mode,
            coord_precision,
            custom_topic,
            include_custom_topic_in_hash=include_custom_topic_in_hash,
        )
        page_id = self._pages.compute_content_hash(hash_key)
        output_path, metadata_path = self._pages.drill_page_paths(page_id)

        cached = self._pages.load_drill_cache(page_id)
        if cached:
            if emit_sse:
                return page_id, output_path, metadata_path, None, None, {"_cached": True, "payload": cached}, None
            return page_id, output_path, metadata_path, None, None, cached, None

        parent_path = self._pages.parent_image_path(parent_id)
        if not parent_path.exists():
            if emit_sse:
                return page_id, output_path, metadata_path, None, None, {}, None
            raise FileNotFoundError(f"Parent image not found: {parent_path}")

        grounding = await self._grounding.isolate_region(
            str(parent_path), x, y, page_id, grounding_mode
        )
        grounding_path = grounding.segment_path or grounding.marked_path
        parent_context = self._load_parent_context(parent_id)

        vision_result, crop_path = await self._drill_context.resolve(
            str(parent_path),
            x,
            y,
            vision_model,
            grounding_mode,
            grounding_path,
            custom_topic,
            parent_context=parent_context,
        )

        return page_id, output_path, metadata_path, parent_path, grounding, vision_result, crop_path

    def _load_parent_context(self, parent_id: str) -> dict | None:
        _, metadata_path = self._pages.drill_page_paths(parent_id)
        if not metadata_path.exists():
            return None
        try:
            with metadata_path.open() as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None

    def _parent_depth(self, parent_id: str) -> int:
        parent_context = self._load_parent_context(parent_id)
        if not parent_context:
            return 0
        depth = parent_context.get("depth")
        return int(depth) if isinstance(depth, int) else 0
