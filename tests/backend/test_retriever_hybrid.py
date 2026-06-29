"""Tests for hybrid retriever boosts."""

from backend.services.knowledge_base.retriever import (
    _apply_content_type_boost,
    _apply_page_proximity_boost,
    _fuse_hybrid_scores,
)


def test_content_type_boost_prefers_figure():
    boosted = _apply_content_type_boost(
        "Technical documentation about pump diagram",
        "figure",
        0.6,
        prefer_content_type="figure",
    )
    assert boosted > 0.6


def test_page_proximity_boost_same_page():
    boosted = _apply_page_proximity_boost(12, 0.6, page_hint=12)
    assert boosted > 0.6


def test_hybrid_fusion_combines_dense_and_sparse():
    dense = [
        {
            "chunk_index": 0,
            "text": "valve specs",
            "page_num": 1,
            "source_name": "m.pdf",
            "score": 0.7,
            "content_type": "text",
            "vector": [1.0, 0.0],
        }
    ]
    sparse = [
        {
            "chunk_index": 1,
            "text": "SV-204-A torque",
            "page_num": 2,
            "content_type": "text",
            "sparse_score": 1.0,
        }
    ]
    fused = _fuse_hybrid_scores(dense, sparse, dense_weight=0.65)
    assert len(fused) == 2
    assert fused[0]["chunk_index"] in (0, 1)
