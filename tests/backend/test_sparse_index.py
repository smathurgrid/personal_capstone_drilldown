"""Tests for BM25 sparse index."""

from pathlib import Path

from backend.services.knowledge_base.sparse_index import (
    build_sparse_index,
    search_sparse,
    tokenize,
)


def test_tokenize_keeps_part_numbers():
    tokens = tokenize("Relief valve SV-204-A rated 150 PSI")
    assert "sv-204-a" in tokens
    assert "150" in tokens


def test_sparse_index_finds_exact_part_number(tmp_path: Path):
    kb_id = "testkb"
    chunks = [
        {"page_num": 1, "text": "Relief valve SV-204-A installation torque 45 Nm", "content_type": "text"},
        {"page_num": 2, "text": "General pump maintenance schedule", "content_type": "text"},
    ]
    build_sparse_index(tmp_path, kb_id, chunks)
    hits = search_sparse("SV-204-A torque", tmp_path, kb_id, top_k=2)
    assert hits
    assert hits[0]["chunk_index"] == 0
    assert hits[0]["sparse_score"] > 0
