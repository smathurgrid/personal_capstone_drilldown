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


def test_drill_cache_round_trip(repository: PageRepository, tmp_path: Path) -> None:
    page_id = repository.compute_content_hash("drill-key")
    image_path, metadata_path = repository.drill_page_paths(page_id)
    image_path.write_bytes(b"png")
    metadata = {"context": "bearing", "metadata": {"object": "Bearing"}}
    repository.save_drill_metadata(metadata_path, metadata)

    cached = repository.load_drill_cache(page_id)
    assert cached is not None
    assert cached["id"] == page_id
    assert cached["context"] == "bearing"
