"""Tests for retriever keyword boost."""

from backend.services.knowledge_base.retriever import _apply_label_keyword_boost


def test_label_keyword_boost_increases_score_for_matching_terms():
    query = "Technical documentation about Relief Valve SV-204-A: regulates pressure"
    boosted = _apply_label_keyword_boost(
        query,
        "Relief valve SV-204-A installation torque 45 Nm",
        0.62,
    )
    assert boosted > 0.62


def test_label_keyword_boost_unchanged_without_label_query():
    score = _apply_label_keyword_boost("generic pump seal text", "valve specs", 0.62)
    assert score == 0.62
