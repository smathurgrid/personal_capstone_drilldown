"""In-memory stash for drills awaiting user confirmation."""

from __future__ import annotations

_pending: dict[str, dict] = {}


def stash(page_id: str, payload: dict) -> None:
    _pending[page_id] = payload


def pop(page_id: str) -> dict | None:
    return _pending.pop(page_id, None)


def discard(page_id: str) -> None:
    _pending.pop(page_id, None)
