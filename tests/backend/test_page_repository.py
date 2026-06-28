"""Explainer page repository unit tests."""

from pathlib import Path

import pytest

from backend.repositories.page_repository import PageRepository


@pytest.fixture
def repository(tmp_path: Path) -> PageRepository:
    return PageRepository(tmp_path)


def test_compute_content_hash_is_deterministic(repository: PageRepository) -> None:
    assert repository.compute_content_hash("topic-a") == repository.compute_content_hash("topic-a")
    assert repository.compute_content_hash("topic-a") != repository.compute_content_hash("topic-b")


def test_initial_page_paths(repository: PageRepository) -> None:
    page_id, image_path = repository.initial_page_paths("turbine engine")
    assert page_id
    assert image_path.name == f"{page_id}.png"
    assert repository.image_url(page_id) == f"/static/{page_id}.png"


def test_page_scan_persistence(repository: PageRepository) -> None:
    page_id = repository.compute_content_hash("upload-key")
    image_path, _metadata_path = repository.drill_page_paths(page_id)
    image_path.write_bytes(b"png")
    repository.save_page_scan(
        page_id,
        metadata={"editorial_headline": "Engine", "granular_details": [{"label": "Turbine"}]},
        raw_json='{"editorial_headline":"Engine"}',
        vision_model="qwen3.5",
        scan_mode="global",
        depth=0,
    )
    loaded = repository.load_page_metadata(page_id)
    assert loaded is not None
    assert loaded["metadata"]["editorial_headline"] == "Engine"
    assert loaded["scanMode"] == "global"


def test_drill_cache_round_trip(repository: PageRepository) -> None:
    page_id = repository.compute_content_hash("drill-key")
    image_path, metadata_path = repository.drill_page_paths(page_id)
    image_path.write_bytes(b"png")
    metadata = {"context": "bearing", "metadata": {"object": "Bearing"}}
    repository.save_drill_metadata(metadata_path, metadata)

    cached = repository.load_drill_cache(page_id)
    assert cached is not None
    assert cached["id"] == page_id
    assert cached["context"] == "bearing"


def test_drill_hash_cache_bust(repository: PageRepository) -> None:
    base = repository.drill_hash_key("parent", 0.5, 0.5, "qwen3.5", "sam2", 4)
    bust = repository.drill_hash_key("parent", 0.5, 0.5, "qwen3.5", "sam2", 4, cache_bust="retry-1")
    assert base != bust


def test_drill_hash_kb_id(repository: PageRepository) -> None:
    no_kb = repository.drill_hash_key("parent", 0.5, 0.5, "qwen3.5", "sam2", 4)
    with_kb = repository.drill_hash_key(
        "parent", 0.5, 0.5, "qwen3.5", "sam2", 4, kb_id="abc123"
    )
    other_kb = repository.drill_hash_key(
        "parent", 0.5, 0.5, "qwen3.5", "sam2", 4, kb_id="def456"
    )
    assert no_kb != with_kb
    assert with_kb != other_kb
