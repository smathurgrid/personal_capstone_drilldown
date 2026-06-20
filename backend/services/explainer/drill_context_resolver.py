"""Resolves drill-down context from custom topics, vision models, or comparisons."""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path

from PIL import Image

from backend.services.explainer.context_analyzer import ContextAnalyzer
from backend.services.explainer.drill_analyzer import DrillAnalyzer
from backend.shared.config import settings
from backend.shared.image_utils import draw_red_ring_b64, path_to_b64, prepare_drill_surfaces

logger = logging.getLogger(__name__)


async def _enrich_with_kb(result: dict, kb_id: str) -> dict:
    """Query the KB with the identified component and enrich result in-place."""
    from backend.services.knowledge_base.retriever import search_kb

    analysis = result.get("analysis", "")
    image_prompt = result.get("image_prompt", "")

    # Build a focused search query from the VLM's analysis
    query = analysis[:300] if analysis else image_prompt[:300]
    if not query.strip():
        return result

    hits = await search_kb(query, kb_id, str(settings.KB_QDRANT_PATH), top_k=4)
    if not hits:
        logger.info("KB search returned no results for kb_id=%s", kb_id)
        return result

    # Pick the top hit (highest score)
    top = hits[0]
    remaining = hits[1:]

    # Enrich image prompt with real KB facts
    kb_facts = top["text"]
    result["image_prompt"] = (
        f"{image_prompt}\n\nAdditional verified context: {kb_facts[:400]}"
    )

    # Build citation string
    citation = f"{top['source_name']}, page {top['page_num']}"

    # Add KB fields to result so they flow into vision dict
    result["kb_description"] = top["text"]
    result["kb_citation"] = citation
    result["kb_score"] = top["score"]
    result["kb_extra_hits"] = [
        {"text": h["text"][:200], "page_num": h["page_num"], "source_name": h["source_name"]}
        for h in remaining
    ]

    logger.info("KB enriched drill: source=%s page=%d score=%.3f", top["source_name"], top["page_num"], top["score"])
    return result


class DrillContextResolver:
    """Selects how drill-down semantic context is produced before image generation."""

    def __init__(
        self,
        context_analyzer: ContextAnalyzer,
        drill_analyzer: DrillAnalyzer,
    ) -> None:
        self._analyzer = context_analyzer
        self._drill_analyzer = drill_analyzer

    @staticmethod
    def _read_parent_bytes(parent_path: str) -> tuple[bytes, int, int]:
        raw = Path(parent_path).read_bytes()
        with Image.open(io.BytesIO(raw)) as img:
            w, h = img.size
        return raw, w, h

    @staticmethod
    def _dual_result_to_vision(
        result: dict,
        *,
        label_hint: str | None = None,
        parent_context: dict | None = None,
    ) -> dict:
        analysis = result.get("analysis", "")
        image_prompt = result.get("image_prompt", "")
        object_name = label_hint or ""
        if not object_name and analysis:
            object_name = analysis.split(".")[0][:80].strip()
        if not object_name:
            object_name = "Selected component"

        headline = f"Drilling into: {object_name}"
        if parent_context:
            parent_meta = parent_context.get("metadata", parent_context)
            if isinstance(parent_meta, dict):
                parent_obj = parent_meta.get("object") or parent_meta.get("editorial_headline")
                if parent_obj:
                    headline = f"{parent_obj} → {object_name}"

        # KB enrichment fields (present only when KB mode is active)
        kb_description = result.get("kb_description")
        kb_citation = result.get("kb_citation")
        kb_score = result.get("kb_score")

        metadata: dict = {
            "object": object_name,
            "editorial_headline": headline,
            "explainer_paragraph": kb_description if kb_description else analysis,
            "drill_topic": image_prompt,
        }
        if kb_citation:
            metadata["kb_citation"] = kb_citation
            metadata["kb_score"] = kb_score
            metadata["kb_mode"] = True

        return {
            "drill_topic": image_prompt,
            "metadata": metadata,
            "input_prompt": "dual-image drill analysis" + (" + KB" if kb_citation else ""),
            "raw_json": json.dumps(
                {
                    "object": object_name,
                    "analysis": analysis,
                    "drill_topic": image_prompt,
                    **({"kb_citation": kb_citation, "kb_score": kb_score} if kb_citation else {}),
                },
                indent=2,
            ),
            "global_b64": result.get("global_b64"),
            "local_crop_b64": result.get("local_crop_b64"),
            "crop_preview_b64": result.get("local_crop_b64"),
        }

    async def _resolve_dual_image(
        self,
        parent_path: str,
        x: float,
        y: float,
        *,
        segment_path: str | None = None,
        marked_path: str | None = None,
        label_hint: str | None = None,
        parent_context: dict | None = None,
        kb_id: str | None = None,
    ) -> tuple[dict, None]:
        raw, w, h = self._read_parent_bytes(parent_path)
        x_px = int(x * w)
        y_px = int(y * h)

        seg = Path(segment_path) if segment_path else None
        marked = Path(marked_path) if marked_path else None

        if seg and seg.exists():
            local_b64 = path_to_b64(seg)
            if marked and marked.exists():
                global_b64 = path_to_b64(marked)
            else:
                global_b64 = draw_red_ring_b64(parent_path, x, y)
        else:
            global_b64, local_b64, _, _ = prepare_drill_surfaces(raw, x_px, y_px, 80)

        result = await self._drill_analyzer.analyze_drill(
            global_b64,
            local_b64,
            label_hint=label_hint,
            parent_context=parent_context,
        )

        # KB enrichment — only when kb_id is provided
        if kb_id:
            result = await _enrich_with_kb(result, kb_id)

        return self._dual_result_to_vision(
            result,
            label_hint=label_hint,
            parent_context=parent_context,
        ), None

    async def resolve(
        self,
        parent_path: str,
        x: float,
        y: float,
        vision_model: str,
        grounding_mode: str,
        grounding_path: str | None,
        custom_topic: str | None,
        parent_context: dict | None = None,
        *,
        segment_path: str | None = None,
        marked_path: str | None = None,
        kb_id: str | None = None,
    ):
        if vision_model == "none":
            crop_b64 = path_to_b64(parent_path)
            try:
                seg = Path(segment_path) if segment_path else None
                if seg and seg.exists():
                    crop_b64 = path_to_b64(seg)
                else:
                    raw, w, h = self._read_parent_bytes(parent_path)
                    x_px, y_px = int(x * w), int(y * h)
                    _, local_b64, _, _ = prepare_drill_surfaces(raw, x_px, y_px, 80)
                    crop_b64 = local_b64
            except OSError:
                pass
            return {
                "drill_topic": (
                    "a detailed macro-zoom into the textures and components of this specific area"
                ),
                "metadata": {
                    "object": custom_topic or "Undefined Component",
                    "editorial_headline": "The Pure Detail",
                    "explainer_paragraph": (
                        "Direct visual drill-down without semantic analysis. "
                        "Generation uses textures and shapes from the grounded region."
                    ),
                    "style": "Visual continuity from previous page",
                },
                "input_prompt": "N/A — vision skipped",
                "raw_json": "{}",
                "crop_preview_b64": crop_b64,
            }, None

        if vision_model == "all":
            models_to_test = ["qwen3.5"]
            results = []
            for model_key in models_to_test:
                try:
                    res, _ = await self._analyzer.identify_drill_context(
                        parent_path, x, y, model_key=model_key, segment_path=grounding_path
                    )
                    results.append(
                        {
                            "model": model_key,
                            "metadata": res.get("metadata", {}),
                            "rawJson": res.get("raw_json", ""),
                        }
                    )
                except Exception as exc:
                    results.append(
                        {"model": model_key, "metadata": {"error": str(exc)}, "rawJson": ""}
                    )
            return {"isComparison": True, "results": results, "groundingMode": grounding_mode}, None

        if custom_topic:
            return await self._resolve_dual_image(
                parent_path,
                x,
                y,
                segment_path=segment_path,
                marked_path=marked_path,
                label_hint=custom_topic,
                parent_context=parent_context,
                kb_id=kb_id,
            )

        return await self._resolve_dual_image(
            parent_path,
            x,
            y,
            segment_path=segment_path,
            marked_path=marked_path,
            parent_context=parent_context,
            kb_id=kb_id,
        )
