"""Resolves drill-down context from custom topics, vision models, or comparisons."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import tempfile
import uuid
from pathlib import Path

from PIL import Image

from backend.services.explainer.context_analyzer import ContextAnalyzer
from backend.services.explainer.drill_analyzer import DrillAnalyzer, PovContextKind
from backend.shared.config import settings
from backend.shared.drill_mode import build_kb_retrieval_snippet, extract_analysis_snippet
from backend.shared.image_utils import (
    b64_to_file,
    compute_drill_crop_radius,
    draw_red_ring_b64,
    path_to_b64,
    prepare_drill_surfaces,
    prepare_wide_context_crop,
)
from backend.shared.llm_client import get_llm_client

logger = logging.getLogger(__name__)


def _comparison_vision_models() -> list[str]:
    configured = os.getenv("EXPLAINER_COMPARISON_MODELS", "").strip()
    if configured:
        return [model.strip() for model in configured.split(",") if model.strip()]
    models: list[str] = []
    for candidate in (settings.EXPLAINER_VISION_MODEL, settings.VISION_MODEL):
        if candidate and candidate not in models:
            models.append(candidate)
    return models or ["qwen3.5"]

_SYNTHESIS_PROMPT = """You are a technical documentation expert reconciling a visual analysis with retrieved manual excerpts.

VISUAL ANALYSIS (from image model):
{analysis}

RETRIEVED MANUAL EXCERPTS:
{kb_facts}

Write a concise, accurate explainer paragraph (3-5 sentences) that:
1. Identifies the component using the best evidence from both sources
2. Corrects any errors in the visual analysis when the manual is more specific
3. Includes relevant specs, part numbers, or procedures from the manual
4. Does not mention "visual analysis" or "manual" — write as a unified expert explanation
5. ONLY include specifications, part numbers, torque values, or procedures that appear in the RETRIEVED MANUAL EXCERPTS above — do not invent details

Component label hint: {label_hint}
"""

_DIAGRAM_QUERY_RE = re.compile(
    r"\b(diagram|schematic|flowchart|figure|drawing|wiring|piping|layout|cross.?section|chart)\b",
    re.IGNORECASE,
)
_PAGE_CITATION_RE = re.compile(r"page\s+(\d+)", re.IGNORECASE)


def _assert_kb_ready(kb_id: str) -> None:
    """Reject drills against a KB that is still ingesting, missing, or has no vectors."""
    from backend.services.knowledge_base import store
    from backend.shared.errors import AppError

    qdrant_path = str(settings.KB_QDRANT_PATH)
    if store.kb_is_ready(settings.KB_DIR, kb_id, qdrant_path=qdrant_path):
        return

    entry = store.get_kb(settings.KB_DIR, kb_id)
    status = entry.get("status", "missing") if entry else "missing"
    if status == "ready":
        status = "missing_collection"
    raise AppError(
        "KB_NOT_READY",
        "Knowledge base is not ready. Wait for PDF ingestion to finish before drilling.",
        status_code=409,
        detail={"kb_id": kb_id, "status": status},
    )


async def _enrich_with_kb(
    result: dict,
    kb_id: str,
    *,
    label_hint: str | None = None,
    drill_mode: str = "inside",
    parent_context: dict | None = None,
) -> dict:
    """Query the KB with the identified component and enrich result in-place."""
    from backend.services.knowledge_base.retriever import search_kb

    query = _build_kb_query(result, label_hint)
    if not query.strip():
        return result

    prefer_content_type = _infer_prefer_content_type(result.get("analysis", ""), label_hint)
    page_hint = _extract_page_hint(parent_context)

    hits = await search_kb(
        query,
        kb_id,
        str(settings.KB_QDRANT_PATH),
        prefer_content_type=prefer_content_type,
        page_hint=page_hint,
    )
    if not hits:
        logger.info("KB search returned no results for kb_id=%s", kb_id)
        result["kb_warning"] = (
            "No matching knowledge base entries found for this component."
        )
        return result

    min_score = settings.KB_MIN_SCORE
    qualified = [h for h in hits if h["score"] >= min_score]
    if not qualified:
        logger.info(
            "KB hits below threshold (%.2f) for kb_id=%s top_score=%.3f",
            min_score,
            kb_id,
            hits[0]["score"],
        )
        result["kb_warning"] = (
            f"No knowledge base entries met the confidence threshold "
            f"(best match: {hits[0]['score']:.0%})."
        )
        return result

    top = qualified[0]
    remaining = qualified[1:]

    kb_facts_parts = [h["text"] for h in qualified[:3]]
    kb_facts = "\n\n".join(kb_facts_parts)

    synthesized = None
    if top["score"] < 0.88:
        synthesized = await _synthesize_kb_context(
            result.get("analysis", ""),
            kb_facts,
            label_hint=label_hint,
        )

    # Panel text gets synthesized KB merge; KB facts stay in kb_description only.
    # Image prompts are not augmented — CLIP token limits (~77) would truncate KB text.
    result["kb_description"] = kb_facts
    result["synthesized_analysis"] = synthesized

    citations: list[str] = []
    seen_pages: set[tuple[str, int]] = set()
    for hit in qualified[:3]:
        key = (hit["source_name"], hit["page_num"])
        if key in seen_pages:
            continue
        seen_pages.add(key)
        citations.append(f"{hit['source_name']}, page {hit['page_num']}")

    result["kb_citation"] = "; ".join(citations) if citations else ""
    result["kb_score"] = top["score"]
    result["kb_extra_hits"] = [
        {
            "text": h["text"][:200],
            "page_num": h["page_num"],
            "source_name": h["source_name"],
            "score": h["score"],
        }
        for h in remaining
    ]

    logger.info(
        "KB enriched drill: source=%s page=%d score=%.3f mode=%s",
        top["source_name"],
        top["page_num"],
        top["score"],
        drill_mode,
    )
    return result


def _build_kb_query(result: dict, label_hint: str | None) -> str:
    """Build a natural-language retrieval query from label hint and VLM analysis."""
    label = label_hint.strip() if label_hint and label_hint.strip() else ""
    analysis = result.get("analysis", "").strip()
    snippet = build_kb_retrieval_snippet(analysis) if analysis else ""

    if label and snippet:
        return f"Technical documentation about {label}: {snippet}"[:400]
    if label:
        return f"Technical documentation about {label}"[:400]
    if snippet:
        return f"Technical documentation: {snippet}"[:400]
    return ""


def _infer_prefer_content_type(analysis: str, label_hint: str | None) -> str | None:
    combined = f"{label_hint or ''} {analysis}"
    if _DIAGRAM_QUERY_RE.search(combined):
        return "figure"
    return None


def _extract_page_hint(parent_context: dict | None) -> int | None:
    if not parent_context:
        return None
    meta = parent_context.get("metadata", parent_context)
    if not isinstance(meta, dict):
        return None
    citation = meta.get("kb_citation") or ""
    match = _PAGE_CITATION_RE.search(str(citation))
    if match:
        return int(match.group(1))
    return None


async def _synthesize_kb_context(
    analysis: str,
    kb_facts: str,
    *,
    label_hint: str | None = None,
) -> str:
    """Reconcile VLM analysis with retrieved KB excerpts via a synthesis LLM pass."""
    analysis = (analysis or "").strip()
    kb_facts = (kb_facts or "").strip()
    if not kb_facts:
        return analysis
    if not analysis:
        return kb_facts

    prompt = _SYNTHESIS_PROMPT.format(
        analysis=analysis,
        kb_facts=kb_facts,
        label_hint=label_hint or "unknown component",
    )
    loop = asyncio.get_running_loop()

    def _run_synthesis() -> str:
        try:
            llm = get_llm_client()
            return llm.chat_completion(
                settings.EXPLAINER_VISION_MODEL,
                prompt,
                temperature=0.1,
                timeout=120,
                num_predict=400,
            ).strip()
        except Exception as exc:
            logger.warning("KB synthesis failed, falling back to merge: %s", exc)
            return ""

    synthesized = await loop.run_in_executor(None, _run_synthesis)
    if synthesized:
        return synthesized
    return _merge_explainer_paragraph(analysis, kb_facts)


def _merge_explainer_paragraph(
    analysis: str,
    kb_description: str | None,
    *,
    kb_score: float | None = None,
    synthesized: str | None = None,
) -> str:
    """Combine VLM analysis with KB excerpt — prefer synthesis when available."""
    if synthesized and synthesized.strip():
        return synthesized.strip()

    analysis = (analysis or "").strip()
    kb_description = (kb_description or "").strip()
    if kb_description and analysis:
        score_note = f" ({kb_score * 100:.0f}% similarity)" if kb_score is not None else ""
        return (
            f"{analysis}\n\n— Retrieved manual excerpt{score_note} —\n{kb_description}"
        )
    return kb_description or analysis


def _pov_suitability_warning(
    parent_context: dict | None,
    *,
    drill_mode: str,
) -> str | None:
    """Warn when POV is unlikely to produce a meaningful outward photograph."""
    if drill_mode != "pov":
        return None

    parent_meta: dict = {}
    if parent_context:
        raw_meta = parent_context.get("metadata", parent_context)
        if isinstance(raw_meta, dict):
            parent_meta = raw_meta

    if parent_meta.get("drill_mode") == "inside":
        return (
            "POV mode follows an inside-view drill. The parent image may be a "
            "cross-section or diagram — outward perspective may look unrealistic."
        )

    paragraph = (parent_meta.get("explainer_paragraph") or "").lower()
    inward_terms = (
        "cross-section",
        "internal",
        "torque",
        "specification",
        "manual excerpt",
        "relief valve specs",
    )
    if any(term in paragraph for term in inward_terms):
        return (
            "POV mode works best on photorealistic scenes. Parent context describes "
            "technical internals — consider inside mode for component detail."
        )
    return None


def _headline_for_mode(drill_mode: str, object_name: str, parent_context: dict | None) -> str:
    if drill_mode == "pov":
        headline = f"Looking outward from: {object_name}"
    else:
        headline = f"Drilling into: {object_name}"

    if parent_context:
        parent_meta = parent_context.get("metadata", parent_context)
        if isinstance(parent_meta, dict):
            parent_obj = parent_meta.get("object") or parent_meta.get("editorial_headline")
            if parent_obj:
                arrow = " → " if drill_mode != "pov" else " · "
                headline = f"{parent_obj}{arrow}{object_name}"
    return headline


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
        drill_mode: str = "inside",
    ) -> dict:
        analysis = result.get("analysis", "")
        image_prompt = result.get("image_prompt", "")
        object_name = label_hint or ""
        if not object_name and analysis:
            object_name = extract_analysis_snippet(analysis, max_len=80)
        if not object_name:
            object_name = "Selected component"

        headline = _headline_for_mode(drill_mode, object_name, parent_context)

        kb_description = result.get("kb_description")
        kb_citation = result.get("kb_citation")
        kb_score = result.get("kb_score")
        kb_warning = result.get("kb_warning")
        kb_extra_hits = result.get("kb_extra_hits") or []
        synthesized = result.get("synthesized_analysis")

        metadata: dict = {
            "object": object_name,
            "editorial_headline": headline,
            "explainer_paragraph": _merge_explainer_paragraph(
                analysis,
                kb_description,
                kb_score=kb_score,
                synthesized=synthesized,
            ),
            "drill_topic": image_prompt,
            "drill_mode": drill_mode,
        }
        if parent_context and isinstance(parent_context.get("ancestry_chain"), list):
            metadata["ancestry_chain"] = list(parent_context["ancestry_chain"])
        else:
            metadata["ancestry_chain"] = []
        if object_name:
            metadata["ancestry_chain"] = [
                *metadata["ancestry_chain"],
                {"object": object_name, "drill_mode": drill_mode},
            ]
        if kb_citation:
            metadata["kb_citation"] = kb_citation
            metadata["kb_score"] = kb_score
            metadata["kb_mode"] = True
        if kb_warning:
            metadata["kb_warning"] = kb_warning
            metadata["kb_mode"] = True
        if kb_extra_hits:
            metadata["kb_extra_hits"] = kb_extra_hits

        pov_warning = _pov_suitability_warning(parent_context, drill_mode=drill_mode)
        if pov_warning:
            metadata["pov_warning"] = pov_warning

        return {
            "drill_topic": image_prompt,
            "metadata": metadata,
            "input_prompt": "dual-image drill analysis" + (" + KB" if kb_citation else ""),
            "raw_json": json.dumps(
                {
                    "object": object_name,
                    "analysis": analysis,
                    "drill_topic": image_prompt,
                    "drill_mode": drill_mode,
                    **({"kb_citation": kb_citation, "kb_score": kb_score} if kb_citation else {}),
                },
                indent=2,
            ),
            "global_b64": result.get("global_b64"),
            "local_crop_b64": result.get("local_crop_b64"),
            "crop_preview_b64": result.get("local_crop_b64"),
            "style_desc": result.get("style_desc", ""),
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
        drill_mode: str = "inside",
        kb_id: str | None = None,
    ) -> tuple[dict, str | None]:
        raw, w, h = self._read_parent_bytes(parent_path)
        x_px = int(x * w)
        y_px = int(y * h)
        crop_radius = compute_drill_crop_radius(w, h)

        seg = Path(segment_path) if segment_path else None
        marked = Path(marked_path) if marked_path else None
        crop_path: str | None = None
        pov_context_kind: PovContextKind = "none"

        if marked and marked.exists():
            global_b64 = path_to_b64(marked)
        else:
            global_b64 = draw_red_ring_b64(parent_path, x, y)

        # POV = look OUT from click — always use wide scene context, never SAM object mask.
        # Inside = macro INTO component — prefer SAM segment, else tight crop.
        if drill_mode == "pov":
            local_b64 = prepare_wide_context_crop(raw, x_px, y_px)
            pov_context_kind = "wide"
            crop_file = Path(tempfile.gettempdir()) / f"drill_pov_{uuid.uuid4().hex}.png"
            b64_to_file(local_b64, crop_file)
            crop_path = str(crop_file)
        elif seg and seg.exists():
            local_b64 = path_to_b64(seg)
            crop_path = str(seg)
        else:
            _, local_b64, _, _ = prepare_drill_surfaces(raw, x_px, y_px, crop_radius)
            crop_file = Path(tempfile.gettempdir()) / f"drill_crop_{uuid.uuid4().hex}.png"
            b64_to_file(local_b64, crop_file)
            crop_path = str(crop_file)

        result = await self._drill_analyzer.analyze_drill(
            global_b64,
            local_b64,
            label_hint=label_hint,
            parent_context=parent_context,
            drill_mode=drill_mode,
            pov_context_kind=pov_context_kind,
        )

        if kb_id:
            result = await _enrich_with_kb(
                result,
                kb_id,
                label_hint=label_hint,
                drill_mode=drill_mode,
                parent_context=parent_context,
            )

        return self._dual_result_to_vision(
            result,
            label_hint=label_hint,
            parent_context=parent_context,
            drill_mode=drill_mode,
        ), crop_path

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
        drill_mode: str = "inside",
        kb_id: str | None = None,
    ):
        if kb_id:
            _assert_kb_ready(kb_id)

        if vision_model == "none":
            crop_b64 = path_to_b64(parent_path)
            try:
                seg = Path(segment_path) if segment_path else None
                if seg and seg.exists():
                    crop_b64 = path_to_b64(seg)
                else:
                    raw, w, h = self._read_parent_bytes(parent_path)
                    x_px, y_px = int(x * w), int(y * h)
                    if drill_mode == "pov":
                        crop_b64 = prepare_wide_context_crop(raw, x_px, y_px)
                    else:
                        crop_radius = compute_drill_crop_radius(w, h)
                        _, local_b64, _, _ = prepare_drill_surfaces(
                            raw, x_px, y_px, crop_radius
                        )
                        crop_b64 = local_b64
            except OSError:
                pass

            if drill_mode == "pov":
                drill_topic = (
                    "A first-person outward-looking photograph from this location in the scene, "
                    "showing the surrounding environment. No text or UI markers in the image."
                )
                headline = "Outward perspective"
                paragraph = (
                    "Direct visual drill-down without semantic analysis. "
                    "Generation produces an outward point-of-view from the selected location."
                )
            else:
                drill_topic = (
                    "a detailed macro-zoom into the textures and components of this specific area"
                )
                headline = "The Pure Detail"
                paragraph = (
                    "Direct visual drill-down without semantic analysis. "
                    "Generation uses textures and shapes from the grounded region."
                )

            return {
                "drill_topic": drill_topic,
                "metadata": {
                    "object": custom_topic or "Undefined Component",
                    "editorial_headline": headline,
                    "explainer_paragraph": paragraph,
                    "drill_mode": drill_mode,
                    "style": "Visual continuity from previous page",
                },
                "input_prompt": "N/A — vision skipped",
                "raw_json": "{}",
                "crop_preview_b64": crop_b64,
            }, None

        if vision_model == "all":
            models_to_test = _comparison_vision_models()
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
                drill_mode=drill_mode,
                kb_id=kb_id,
            )

        return await self._resolve_dual_image(
            parent_path,
            x,
            y,
            segment_path=segment_path,
            marked_path=marked_path,
            parent_context=parent_context,
            drill_mode=drill_mode,
            kb_id=kb_id,
        )
