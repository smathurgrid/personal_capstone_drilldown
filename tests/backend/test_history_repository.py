"""Drill history repository unit tests."""

from backend.repositories.history_repository import HistoryRepository


def test_append_and_list() -> None:
    repo = HistoryRepository()
    node = {"id": "n1", "x": 0.5, "y": 0.5}
    repo.append(node)
    assert repo.list_all() == [node]


def test_clear() -> None:
    repo = HistoryRepository()
    repo.append({"id": "n1"})
    repo.clear()
    assert repo.list_all() == []
