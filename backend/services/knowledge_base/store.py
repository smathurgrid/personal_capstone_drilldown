"""KB registry — tracks uploaded knowledge bases in a JSON file."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _registry_path(kb_dir: Path) -> Path:
    return kb_dir / "registry.json"


def _load(kb_dir: Path) -> list[dict]:
    p = _registry_path(kb_dir)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []


def _save(kb_dir: Path, entries: list[dict]) -> None:
    kb_dir.mkdir(parents=True, exist_ok=True)
    _registry_path(kb_dir).write_text(json.dumps(entries, indent=2))


def list_kbs(kb_dir: Path) -> list[dict]:
    return _load(kb_dir)


def get_kb(kb_dir: Path, kb_id: str) -> dict | None:
    return next((e for e in _load(kb_dir) if e["id"] == kb_id), None)


def register_kb(kb_dir: Path, kb_id: str, name: str, page_count: int) -> dict:
    entries = _load(kb_dir)
    entries = [e for e in entries if e["id"] != kb_id]
    entry = {
        "id": kb_id,
        "name": name,
        "page_count": page_count,
        "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    entries.append(entry)
    _save(kb_dir, entries)
    return entry


def register_kb_pending(kb_dir: Path, kb_id: str, name: str) -> dict:
    entries = _load(kb_dir)
    entries = [e for e in entries if e["id"] != kb_id]
    entry = {
        "id": kb_id,
        "name": name,
        "page_count": 0,
        "status": "processing",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    entries.append(entry)
    _save(kb_dir, entries)
    return entry


def update_kb_status(
    kb_dir: Path,
    kb_id: str,
    *,
    status: str,
    page_count: int | None = None,
    chunk_count: int | None = None,
    figure_count: int | None = None,
    error: str | None = None,
    ingest_stats: dict | None = None,
) -> dict | None:
    entries = _load(kb_dir)
    updated = None
    for entry in entries:
        if entry["id"] == kb_id:
            entry["status"] = status
            if page_count is not None:
                entry["page_count"] = page_count
            if chunk_count is not None:
                entry["chunk_count"] = chunk_count
            if figure_count is not None:
                entry["figure_count"] = figure_count
            if ingest_stats is not None:
                entry["ingest_stats"] = ingest_stats
            if error:
                entry["error"] = error
            elif "error" in entry:
                del entry["error"]
            updated = entry
            break
    if updated:
        _save(kb_dir, entries)
    return updated


def remove_kb(kb_dir: Path, kb_id: str) -> None:
    entries = [e for e in _load(kb_dir) if e["id"] != kb_id]
    _save(kb_dir, entries)


def kb_exists(kb_dir: Path, kb_id: str) -> bool:
    return any(e["id"] == kb_id for e in _load(kb_dir))


def kb_is_ready(kb_dir: Path, kb_id: str, *, qdrant_path: str | None = None) -> bool:
    entry = get_kb(kb_dir, kb_id)
    if entry is None:
        return False
    status = entry.get("status", "ready")
    if status != "ready":
        return False
    if qdrant_path is None:
        return True
    from backend.services.knowledge_base.qdrant_client import collection_exists

    return collection_exists(qdrant_path, f"kb_{kb_id}")
