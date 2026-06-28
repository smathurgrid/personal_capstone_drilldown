"""Tests for KB query construction, enrichment, and readiness guards."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.models.explainer import PageRequest
from backend.services.explainer.drill_context_resolver import (
    _assert_kb_ready,
    _build_kb_query,
    _enrich_with_kb,
    _merge_explainer_paragraph,
    _pov_suitability_warning,
)
from backend.services.knowledge_base import store
from backend.shared.drill_mode import (
    build_kb_retrieval_snippet,
    extract_analysis_snippet,
    normalize_drill_mode,
)
from backend.shared.errors import AppError


def test_pov_suitability_warning_after_inside_parent():
    warning = _pov_suitability_warning(
        {"metadata": {"drill_mode": "inside", "explainer_paragraph": "Cross-section view."}},
        drill_mode="pov",
    )
    assert warning is not None
    assert "inside-view" in warning


def test_pov_suitability_warning_none_for_inside_mode():
    assert _pov_suitability_warning(None, drill_mode="inside") is None


def test_build_kb_query_prefers_label_hint():
    result = {
        "analysis": "The relief valve regulates pressure in the main line.",
        "image_prompt": "Cross-section of valve internals",
    }
    query = _build_kb_query(result, "Relief Valve SV-204-A")
    assert query.startswith("Technical documentation about Relief Valve SV-204-A:")
    assert "relief valve" in query.lower()


def test_build_kb_query_handles_figure_reference():
    result = {
        "analysis": "Fig. 3.2 shows the relief valve assembly on the pump inlet.",
        "image_prompt": "POV outward",
    }
    query = _build_kb_query(result, None)
    assert query.startswith("Technical documentation:")
    assert query != "Fig"
    assert "relief valve" in query.lower()


def test_build_kb_query_ignores_image_prompt_fallback():
    result = {
        "analysis": "",
        "image_prompt": "photorealistic cross-section with dramatic overhead lighting",
    }
    query = _build_kb_query(result, None)
    assert query == ""


def test_build_kb_retrieval_snippet_includes_multiple_sentences():
    analysis = (
        "This is a hydraulic component in the pump assembly. "
        "Part number RV-240 regulates pressure at 150 PSI. "
        "Installation requires torque of 45 Nm."
    )
    snippet = build_kb_retrieval_snippet(analysis)
    assert "RV-240" in snippet
    assert "hydraulic component" in snippet


def test_extract_analysis_snippet_preserves_decimals():
    snippet = extract_analysis_snippet("3.5 mm clearance required at the seal face.")
    assert snippet.startswith("3.5 mm")


def test_normalize_drill_mode_aliases():
    assert normalize_drill_mode("POV") == "pov"
    assert normalize_drill_mode("perspective") == "pov"
    assert normalize_drill_mode("inside") == "inside"


def test_page_request_rejects_invalid_drill_mode():
    with pytest.raises(ValueError):
        PageRequest(drillMode="zoomed-in")


def test_page_request_accepts_perspective_alias():
    req = PageRequest(drillMode="perspective")
    assert req.drillMode == "pov"


def test_merge_explainer_paragraph_keeps_both_sources():
    merged = _merge_explainer_paragraph(
        "VLM says this is a pressure relief valve.",
        "Manual: SV-204-A rated to 150 PSI.",
        kb_score=0.78,
    )
    assert "VLM says" in merged
    assert "Manual:" in merged
    assert "Retrieved manual excerpt" in merged
    assert "78% similarity" in merged


def test_merge_explainer_paragraph_prefers_synthesis():
    merged = _merge_explainer_paragraph(
        "VLM says relief valve.",
        "Manual: SV-204-A rated to 150 PSI.",
        synthesized="The SV-204-A relief valve regulates pressure to 150 PSI.",
    )
    assert merged == "The SV-204-A relief valve regulates pressure to 150 PSI."


def test_merge_explainer_paragraph_analysis_only():
    assert _merge_explainer_paragraph("Analysis only.", None) == "Analysis only."


@pytest.mark.asyncio
async def test_enrich_with_kb_applies_score_threshold():
    result = {"analysis": "Pump seal", "image_prompt": "Seal cross-section"}
    hits = [
        {"text": "Weak hit", "page_num": 1, "source_name": "manual.pdf", "score": 0.42},
    ]
    with patch(
        "backend.services.knowledge_base.retriever.search_kb",
        new=AsyncMock(return_value=hits),
    ):
        enriched = await _enrich_with_kb(result, "kb123", label_hint="Pump seal")

    assert "kb_warning" in enriched
    assert "kb_citation" not in enriched
    assert enriched["image_prompt"] == "Seal cross-section"


@pytest.mark.asyncio
async def test_enrich_with_kb_fuses_qualified_hits_inside_mode():
    result = {"analysis": "Relief valve", "image_prompt": "Cross-section view"}
    hits = [
        {"text": "Section 4.2 Relief Valve specs.", "page_num": 12, "source_name": "m.pdf", "score": 0.78},
        {"text": "Installation torque 45 Nm.", "page_num": 13, "source_name": "m.pdf", "score": 0.71},
    ]
    with (
        patch(
            "backend.services.knowledge_base.retriever.search_kb",
            new=AsyncMock(return_value=hits),
        ),
        patch(
            "backend.services.explainer.drill_context_resolver._synthesize_kb_context",
            new=AsyncMock(return_value="Synthesized relief valve explanation."),
        ),
    ):
        enriched = await _enrich_with_kb(
            result, "kb123", label_hint="Relief Valve", drill_mode="inside"
        )

    assert enriched["kb_score"] == 0.78
    assert enriched["kb_citation"] == "m.pdf, page 12; m.pdf, page 13"
    assert enriched["synthesized_analysis"] == "Synthesized relief valve explanation."
    assert enriched["image_prompt"] == "Cross-section view"


@pytest.mark.asyncio
async def test_enrich_with_kb_skips_image_prompt_for_pov():
    result = {"analysis": "Window view", "image_prompt": "Outward POV photograph from window"}
    hits = [
        {"text": "Torque spec 45 Nm.", "page_num": 2, "source_name": "m.pdf", "score": 0.8},
    ]
    with (
        patch(
            "backend.services.knowledge_base.retriever.search_kb",
            new=AsyncMock(return_value=hits),
        ),
        patch(
            "backend.services.explainer.drill_context_resolver._synthesize_kb_context",
            new=AsyncMock(return_value="Synthesized window context."),
        ),
    ):
        enriched = await _enrich_with_kb(result, "kb123", drill_mode="pov")

    assert enriched["image_prompt"] == "Outward POV photograph from window"
    assert "Torque spec" in enriched["kb_description"]


def test_assert_kb_ready_rejects_processing(tmp_path, monkeypatch):
    from backend.shared import config

    monkeypatch.setattr(config.settings, "KB_DIR", tmp_path)
    monkeypatch.setattr(config.settings, "KB_QDRANT_PATH", tmp_path / "qdrant")
    kb_id = "abc123"
    store.register_kb_pending(tmp_path, kb_id, "manual.pdf")

    with patch(
        "backend.services.knowledge_base.qdrant_client.collection_exists",
        return_value=False,
    ):
        with pytest.raises(AppError) as exc_info:
            _assert_kb_ready(kb_id)

    assert exc_info.value.code == "KB_NOT_READY"
    assert exc_info.value.detail["status"] == "processing"


def test_assert_kb_ready_requires_collection(tmp_path, monkeypatch):
    from backend.shared import config

    monkeypatch.setattr(config.settings, "KB_DIR", tmp_path)
    monkeypatch.setattr(config.settings, "KB_QDRANT_PATH", tmp_path / "qdrant")
    kb_id = "ready123"
    store.register_kb(tmp_path, kb_id, "manual.pdf", page_count=10)

    with patch(
        "backend.services.knowledge_base.qdrant_client.collection_exists",
        return_value=False,
    ):
        with pytest.raises(AppError) as exc_info:
            _assert_kb_ready(kb_id)

    assert exc_info.value.detail["status"] == "missing_collection"


def test_assert_kb_ready_allows_ready_kb_with_collection(tmp_path, monkeypatch):
    from backend.shared import config

    monkeypatch.setattr(config.settings, "KB_DIR", tmp_path)
    monkeypatch.setattr(config.settings, "KB_QDRANT_PATH", tmp_path / "qdrant")
    kb_id = "ready123"
    store.register_kb(tmp_path, kb_id, "manual.pdf", page_count=10)

    with patch(
        "backend.services.knowledge_base.qdrant_client.collection_exists",
        return_value=True,
    ):
        _assert_kb_ready(kb_id)


def test_infer_prefer_content_type_for_diagram():
    from backend.services.explainer.drill_context_resolver import _infer_prefer_content_type

    assert _infer_prefer_content_type("This wiring schematic shows the control panel", None) == "figure"
    assert _infer_prefer_content_type("Hydraulic pump seal", None) is None


def test_extract_page_hint_from_parent_citation():
    from backend.services.explainer.drill_context_resolver import _extract_page_hint

    hint = _extract_page_hint({"metadata": {"kb_citation": "manual.pdf, page 47"}})
    assert hint == 47


@pytest.mark.asyncio
async def test_enrich_with_kb_passes_retrieval_hints():
    result = {"analysis": "Wiring diagram for control panel", "image_prompt": "Cross-section"}
    hits = [
        {
            "text": "Panel wiring diagram Fig 4.2",
            "page_num": 4,
            "source_name": "m.pdf",
            "score": 0.82,
            "content_type": "figure",
        },
    ]

    async def _fake_search(*args, **kwargs):
        assert kwargs.get("prefer_content_type") == "figure"
        assert kwargs.get("page_hint") == 3
        return hits

    with (
        patch(
            "backend.services.knowledge_base.retriever.search_kb",
            new=AsyncMock(side_effect=_fake_search),
        ),
        patch(
            "backend.services.explainer.drill_context_resolver._synthesize_kb_context",
            new=AsyncMock(return_value="Synthesized panel wiring."),
        ),
    ):
        enriched = await _enrich_with_kb(
            result,
            "kb123",
            parent_context={"metadata": {"kb_citation": "m.pdf, page 3"}},
        )

    assert enriched["synthesized_analysis"] == "Synthesized panel wiring."
