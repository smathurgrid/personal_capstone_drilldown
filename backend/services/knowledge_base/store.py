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


def register_kb(kb_dir: Path, kb_id: str, name: str, page_count: int) -> dict:
    entries = _load(kb_dir)
    # Remove existing entry with same id if re-uploading
    entries = [e for e in entries if e["id"] != kb_id]
    entry = {
        "id": kb_id,
        "name": name,
        "page_count": page_count,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    entries.append(entry)
    _save(kb_dir, entries)
    return entry


def remove_kb(kb_dir: Path, kb_id: str) -> None:
    entries = [e for e in _load(kb_dir) if e["id"] != kb_id]
    _save(kb_dir, entries)


def kb_exists(kb_dir: Path, kb_id: str) -> bool:
    return any(e["id"] == kb_id for e in _load(kb_dir))
