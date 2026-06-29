"""Explainer page workflow orchestration (topic, drill-down, streaming)."""

import json

from backend.core.protocols import (
    ExplainerPageStore,
    ExplainerPageWorkflow,
    ImageGenerator,
)
from backend.services.explainer.pending_drill_store import discard as discard_pending_drill
from backend.services.explainer.pending_drill_store import pop as pop_pending_drill
from backend.services.explainer.pending_drill_store import stash as stash_pending_drill
from backend.services.explainer.drill_context_resolver import (
    DrillContextResolver,
    _assert_kb_ready,
)
from backend.services.explainer.grounding_service import GroundingService
from backend.services.explainer.drill_workflow import (
    DrillWorkflow,
    build_result_metadata,
    extract_vision_fields,
)
from backend.services.explainer.stream_events import format_sse_event
from backend.shared.errors import AppError
from backend.shared.generation_bridge import generate_topic_image_to_file
from backend.shared.ollama_health import require_ollama


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
        cache_bust: str | None = None,
        drill_mode: str = "inside",
        kb_id: str | None = None,
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
            raise AppError(
                "DRILL_USE_STREAM",
                "Drill operations must use POST /stream-page and POST /confirm-drill. "
                "Sync POST /page drill is deprecated.",
                status_code=400,
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
        cache_bust: str | None = None,
        drill_mode: str = "inside",
        kb_id: str | None = None,
    ):
        if query:
            try:
                require_ollama()
                yield format_sse_event("generating", {"message": "Generating initial image..."})
                page_id, output_path = self._pages.initial_page_paths(query)
                if not output_path.exists():
                    await generate_topic_image_to_file(
                        query, output_path, image_generator=self._image_generator
                    )
                yield format_sse_event(
                    "complete", {"id": page_id, "imageUrl": self._pages.image_url(page_id)}
                )
            except AppError as exc:
                yield format_sse_event(
                    "error",
                    {"message": exc.message, "code": exc.code, "detail": exc.detail},
                )
            except Exception as exc:
                yield format_sse_event(
                    "error",
                    {"message": str(exc), "code": "GENERATION_FAILED"},
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
                cache_bust=cache_bust,
                drill_mode=drill_mode,
                kb_id=kb_id,
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
        cache_bust: str | None = None,
        drill_mode: str = "inside",
        kb_id: str | None = None,
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
                cache_bust=cache_bust,
                drill_mode=drill_mode,
                kb_id=kb_id,
            )
        )

        if parent_path is None and isinstance(vision_result, dict) and vision_result.get("id"):
            return vision_result

        if vision_result.get("isComparison"):
            return {"id": page_id, "imageUrl": self._pages.image_url(parent_id), **vision_result}

        drill_topic, metadata, input_prompt, raw_json = extract_vision_fields(vision_result)
        parent_depth = self._depth_from_context(
            self._load_parent_context(parent_id)
        )
        result_metadata = self._build_drill_metadata(
            parent_id,
            x,
            y,
            vision_model,
            grounding_mode,
            grounding,
            drill_topic,
            metadata,
            input_prompt,
            raw_json,
            parent_depth=parent_depth,
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
            drill_mode=drill_mode,
            style_desc=vision_result.get("style_desc", ""),
        )

    async def _stream_drill(
        self,
        parent_id: str,
        x: float,
        y: float,
        vision_model: str,
        grounding_mode: str,
        custom_topic: str | None,
        cache_bust: str | None = None,
        drill_mode: str = "inside",
        kb_id: str | None = None,
    ):
        try:
            preamble = self._drill_preamble(
                parent_id,
                x,
                y,
                vision_model,
                grounding_mode,
                custom_topic,
                coord_precision=self._DRILL_COORD_PRECISION,
                include_custom_topic_in_hash=self._DRILL_INCLUDE_CUSTOM_TOPIC_IN_HASH,
                cache_bust=cache_bust,
                drill_mode=drill_mode,
                kb_id=kb_id,
            )
        except AppError as exc:
            yield format_sse_event(
                "error",
                {"message": exc.message, "code": exc.code, "detail": exc.detail},
            )
            return

        try:
            if preamble.get("cached"):
                cached = preamble["payload"]
                page_id = preamble["page_id"]
                meta = cached.get("metadata", {})
                if isinstance(meta, dict) and isinstance(meta.get("metadata"), dict):
                    meta = meta["metadata"]
                drill_topic = (
                    cached.get("context")
                    or (meta.get("drill_topic") if isinstance(meta, dict) else None)
                    or ""
                )
                object_name = "Selected region"
                if isinstance(meta, dict):
                    object_name = (
                        meta.get("object")
                        or meta.get("editorial_headline")
                        or object_name
                    )
                expires_at = stash_pending_drill(
                    page_id,
                    {
                        "page_id": page_id,
                        "from_cache": True,
                        "cached_payload": cached,
                        "drill_topic": drill_topic,
                        "drill_mode": drill_mode,
                    },
                )
                confirm_payload = self._build_confirm_payload(
                    page_id=page_id,
                    parent_id=parent_id,
                    x=x,
                    y=y,
                    object_name=object_name,
                    drill_topic=drill_topic,
                    metadata=meta if isinstance(meta, dict) else {},
                    drill_mode=drill_mode,
                    grounding_mode=grounding_mode,
                    expires_at=expires_at,
                    from_cache=True,
                    image_url=cached.get("imageUrl"),
                )
                yield format_sse_event("confirm", confirm_payload)
                return

            page_id = preamble["page_id"]
            output_path = preamble["output_path"]
            metadata_path = preamble["metadata_path"]
            parent_path = preamble["parent_path"]
            parent_context = preamble["parent_context"]
            parent_depth = preamble["parent_depth"]

            if parent_path is None:
                yield format_sse_event("error", {"message": "Parent image not found."})
                return

            require_ollama()

            effective_grounding = "red_ring" if drill_mode == "inside" else grounding_mode

            yield format_sse_event("grounding", {"message": "Isolating object..."})
            grounding = await self._grounding.isolate_region(
                str(parent_path), x, y, page_id, effective_grounding
            )
            grounding_path = grounding.segment_path or grounding.marked_path

            yield format_sse_event(
                "vision",
                {"message": "Analyzing component...", "samConfidence": grounding.confidence},
            )
            vision_result, crop_path = await self._drill_context.resolve(
                str(parent_path),
                x,
                y,
                vision_model,
                grounding_mode,
                grounding_path,
                custom_topic,
                parent_context=parent_context,
                segment_path=grounding.segment_path,
                marked_path=grounding.marked_path,
                drill_mode=drill_mode,
                kb_id=kb_id,
            )

            drill_topic, metadata, input_prompt, raw_json = extract_vision_fields(vision_result)
            result_metadata = self._build_drill_metadata(
                parent_id,
                x,
                y,
                vision_model,
                grounding_mode,
                grounding,
                drill_topic,
                metadata,
                input_prompt,
                raw_json,
                parent_depth=parent_depth,
            )

            crop_preview = vision_result.get("crop_preview_b64") or vision_result.get("local_crop_b64")
            object_name = metadata.get("object") or metadata.get("editorial_headline") or "Selected region"

            expires_at = stash_pending_drill(
                page_id,
                {
                    "page_id": page_id,
                    "output_path": str(output_path),
                    "metadata_path": str(metadata_path),
                    "parent_path": str(parent_path),
                    "x": x,
                    "y": y,
                    "drill_topic": drill_topic,
                    "segment_path": grounding.segment_path,
                    "marked_path": grounding.marked_path,
                    "crop_path": crop_path,
                    "result_metadata": result_metadata,
                    "drill_mode": drill_mode,
                    "style_desc": vision_result.get("style_desc", ""),
                },
            )

            confirm_payload = self._build_confirm_payload(
                page_id=page_id,
                parent_id=parent_id,
                x=x,
                y=y,
                object_name=object_name,
                drill_topic=drill_topic,
                metadata=metadata,
                drill_mode=drill_mode,
                grounding_mode=grounding_mode,
                grounding_confidence=grounding.confidence,
                crop_preview=crop_preview,
                raw_json=raw_json,
                input_prompt=input_prompt,
                expires_at=expires_at,
            )
            yield format_sse_event("confirm", confirm_payload)
        except AppError as exc:
            yield format_sse_event(
                "error",
                {"message": exc.message, "code": exc.code, "detail": exc.detail},
            )
        except Exception as exc:
            yield format_sse_event(
                "error",
                {"message": str(exc), "code": "DRILL_FAILED"},
            )

    async def confirm_drill(self, page_id: str, drill_topic: str | None = None):
        pending = pop_pending_drill(page_id)
        if not pending:
            raise AppError(
                "DRILL_SESSION_EXPIRED",
                "Drill session expired or not found. Please drill again.",
                status_code=410,
            )

        if pending.get("from_cache"):
            return pending["cached_payload"]

        topic = drill_topic or pending["drill_topic"]
        result_metadata = dict(pending["result_metadata"])
        result_metadata["context"] = topic
        if drill_topic:
            meta = dict(result_metadata.get("metadata", {}))
            meta["drill_topic"] = drill_topic
            original_topic = (pending.get("drill_topic") or "").strip()
            if drill_topic.strip() != original_topic:
                meta["topic_overridden"] = True
                for kb_field in (
                    "kb_citation",
                    "kb_score",
                    "kb_warning",
                    "kb_extra_hits",
                    "kb_mode",
                ):
                    meta.pop(kb_field, None)
            result_metadata["metadata"] = meta

        return await self._drill_workflow.complete_drill(
            pending["page_id"],
            pending["output_path"],
            pending["metadata_path"],
            topic,
            pending["parent_path"],
            pending["x"],
            pending["y"],
            pending.get("segment_path"),
            pending.get("marked_path"),
            pending.get("crop_path"),
            result_metadata,
            drill_mode=pending.get("drill_mode", "inside"),
            style_desc=pending.get("style_desc", ""),
        )

    def cancel_drill(self, page_id: str) -> None:
        discard_pending_drill(page_id)

    def get_page(self, page_id: str) -> dict:
        cached = self._pages.load_drill_cache(page_id)
        if cached:
            meta = cached.get("metadata", {})
            if isinstance(meta, dict) and meta.get("editorial_headline"):
                cached["metadata"] = meta
            return cached
        stored = self._pages.load_page_metadata(page_id)
        if stored:
            return stored
        image_path = self._pages.page_image_path(page_id)
        if not image_path.exists():
            raise FileNotFoundError(f"Page not found: {page_id}")
        return {
            "id": page_id,
            "imageUrl": self._pages.image_url(page_id),
            "metadata": {},
            "depth": 0,
        }

    def _build_drill_metadata(
        self,
        parent_id: str,
        x: float,
        y: float,
        vision_model: str,
        grounding_mode: str,
        grounding,
        drill_topic: str,
        metadata: dict,
        input_prompt: str,
        raw_json: str,
        *,
        parent_depth: int | None = None,
    ) -> dict:
        result_metadata = build_result_metadata(
            drill_topic,
            metadata,
            input_prompt,
            raw_json,
            grounding.confidence,
            grounding_mode,
        )
        depth = parent_depth if parent_depth is not None else self._parent_depth(parent_id)
        result_metadata.update(
            {
                "parentId": parent_id,
                "click": {"x": x, "y": y},
                "visionModel": vision_model,
                "groundingMode": grounding_mode,
                "depth": depth + 1,
            }
        )
        return result_metadata

    def _drill_preamble(
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
        cache_bust: str | None = None,
        drill_mode: str = "inside",
        kb_id: str | None = None,
    ) -> dict:
        if kb_id:
            _assert_kb_ready(kb_id)

        hash_key = self._pages.drill_hash_key(
            parent_id,
            x,
            y,
            vision_model,
            grounding_mode,
            coord_precision,
            custom_topic,
            include_custom_topic_in_hash=include_custom_topic_in_hash,
            cache_bust=cache_bust,
            drill_mode=drill_mode,
            kb_id=kb_id,
        )
        page_id = self._pages.compute_content_hash(hash_key)
        output_path, metadata_path = self._pages.drill_page_paths(page_id)

        cached = self._pages.load_drill_cache(page_id)
        if cached:
            return {
                "cached": True,
                "payload": cached,
                "page_id": page_id,
                "output_path": output_path,
                "metadata_path": metadata_path,
            }

        parent_path = self._pages.parent_image_path(parent_id)
        if not parent_path.exists():
            return {
                "cached": False,
                "page_id": page_id,
                "output_path": output_path,
                "metadata_path": metadata_path,
                "parent_path": None,
                "parent_context": None,
                "parent_depth": 0,
            }

        parent_context = self._load_parent_context(parent_id)
        if parent_context is not None:
            parent_context = dict(parent_context)
            parent_context["ancestry_chain"] = self._build_ancestry_chain(parent_id)
        return {
            "cached": False,
            "page_id": page_id,
            "output_path": output_path,
            "metadata_path": metadata_path,
            "parent_path": parent_path,
            "parent_context": parent_context,
            "parent_depth": self._depth_from_context(parent_context),
        }

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
        cache_bust: str | None = None,
        drill_mode: str = "inside",
        kb_id: str | None = None,
    ):
        preamble = self._drill_preamble(
            parent_id,
            x,
            y,
            vision_model,
            grounding_mode,
            custom_topic,
            coord_precision=coord_precision,
            include_custom_topic_in_hash=include_custom_topic_in_hash,
            cache_bust=cache_bust,
            drill_mode=drill_mode,
            kb_id=kb_id,
        )

        if preamble.get("cached"):
            cached = preamble["payload"]
            page_id = preamble["page_id"]
            output_path = preamble["output_path"]
            metadata_path = preamble["metadata_path"]
            if emit_sse:
                return page_id, output_path, metadata_path, None, None, {"_cached": True, "payload": cached}, None
            return page_id, output_path, metadata_path, None, None, cached, None

        page_id = preamble["page_id"]
        output_path = preamble["output_path"]
        metadata_path = preamble["metadata_path"]
        parent_path = preamble["parent_path"]
        parent_context = preamble["parent_context"]

        if parent_path is None:
            if emit_sse:
                return page_id, output_path, metadata_path, None, None, {}, None
            raise FileNotFoundError(f"Parent image not found for parent_id={parent_id}")

        effective_grounding = "red_ring" if drill_mode == "inside" else grounding_mode
        grounding = await self._grounding.isolate_region(
            str(parent_path), x, y, page_id, effective_grounding
        )
        grounding_path = grounding.segment_path or grounding.marked_path

        vision_result, crop_path = await self._drill_context.resolve(
            str(parent_path),
            x,
            y,
            vision_model,
            grounding_mode,
            grounding_path,
            custom_topic,
            parent_context=parent_context,
            segment_path=grounding.segment_path,
            marked_path=grounding.marked_path,
            drill_mode=drill_mode,
            kb_id=kb_id,
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

    @staticmethod
    def _depth_from_context(parent_context: dict | None) -> int:
        if not parent_context:
            return 0
        depth = parent_context.get("depth")
        return int(depth) if isinstance(depth, int) else 0

    def _parent_depth(self, parent_id: str) -> int:
        return self._depth_from_context(self._load_parent_context(parent_id))

    def _build_ancestry_chain(
        self, parent_id: str, *, max_levels: int = 5
    ) -> list[dict[str, str]]:
        """Walk parentId chain for drill-path context (root → immediate parent)."""
        chain: list[dict[str, str]] = []
        current: str | None = parent_id
        for _ in range(max_levels):
            if not current:
                break
            ctx = self._load_parent_context(current)
            if not ctx:
                break
            meta = ctx.get("metadata", ctx)
            if isinstance(meta, dict):
                obj = (
                    meta.get("object")
                    or meta.get("editorial_headline")
                    or meta.get("title")
                )
                mode = str(
                    meta.get("drill_mode") or ctx.get("drill_mode") or "inside"
                )
                if obj and str(obj).strip():
                    chain.insert(0, {"object": str(obj).strip(), "drill_mode": mode})
            parent = ctx.get("parentId")
            current = str(parent) if parent else None
        return chain

    @staticmethod
    def _build_confirm_payload(
        *,
        page_id: str,
        parent_id: str,
        x: float,
        y: float,
        object_name: str,
        drill_topic: str,
        metadata: dict,
        drill_mode: str,
        grounding_mode: str,
        expires_at: str,
        from_cache: bool = False,
        image_url: str | None = None,
        grounding_confidence: float | None = None,
        crop_preview: str | None = None,
        raw_json: str | None = None,
        input_prompt: str | None = None,
    ) -> dict:
        payload: dict = {
            "pageId": page_id,
            "parentId": parent_id,
            "click": {"x": x, "y": y},
            "objectName": object_name,
            "drillTopic": drill_topic,
            "metadata": metadata,
            "groundingMode": grounding_mode,
            "drillMode": drill_mode,
            "expiresAt": expires_at,
            "fromCache": from_cache,
        }
        if image_url:
            payload["imageUrl"] = image_url
        if crop_preview:
            payload["cropPreviewB64"] = crop_preview
        if grounding_confidence is not None:
            payload["samConfidence"] = grounding_confidence
        if raw_json is not None:
            payload["rawJson"] = raw_json
        if input_prompt is not None:
            payload["inputPrompt"] = input_prompt
        if metadata.get("kb_citation"):
            payload["kbCitation"] = metadata["kb_citation"]
        if metadata.get("kb_score") is not None:
            payload["kbScore"] = metadata["kb_score"]
        if metadata.get("kb_warning"):
            payload["kbWarning"] = metadata["kb_warning"]
        if metadata.get("kb_extra_hits"):
            payload["kbExtraHits"] = metadata["kb_extra_hits"]
        if metadata.get("explainer_paragraph"):
            payload["explainerParagraph"] = metadata["explainer_paragraph"]
        ancestry = metadata.get("ancestry_chain")
        if isinstance(ancestry, list) and ancestry:
            payload["ancestryChain"] = ancestry
        return payload
