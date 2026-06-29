"""File-backed stash for drills awaiting user confirmation (survives process restart)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.shared.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 30 * 60  # 30 minutes


def _pending_dir() -> Path:
    path = settings.EXPLAINER_STATIC_DIR.parent / "pending"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _entry_path(page_id: str) -> Path:
    safe_id = page_id.replace("/", "_")
    return _pending_dir() / f"{safe_id}.json"


def _parse_ts(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _is_expired(entry: dict) -> bool:
    expires_at = entry.get("expires_at")
    if not expires_at:
        return False
    exp = _parse_ts(str(expires_at))
    if exp is None:
        return True
    return datetime.now(timezone.utc) > exp


def prune_expired() -> int:
    """Remove expired pending entries. Returns count removed."""
    removed = 0
    for path in _pending_dir().glob("*.json"):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            if _is_expired(entry):
                path.unlink(missing_ok=True)
                removed += 1
        except (OSError, json.JSONDecodeError):
            path.unlink(missing_ok=True)
            removed += 1
    if removed:
        logger.info("Pruned %d expired pending drill session(s)", removed)
    return removed


def stash(
    page_id: str,
    payload: dict,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> str:
    """Persist a pending drill. Returns ISO8601 expires_at."""
    prune_expired()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=ttl_seconds)
    entry = {
        **payload,
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
    }
    _entry_path(page_id).write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return expires.isoformat()


def pop(page_id: str) -> dict | None:
    """Load and remove a pending drill if present and not expired."""
    prune_expired()
    path = _entry_path(page_id)
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        path.unlink(missing_ok=True)
        return None
    path.unlink(missing_ok=True)
    if _is_expired(entry):
        return None
    entry.pop("created_at", None)
    entry.pop("expires_at", None)
    return entry


def discard(page_id: str) -> None:
    _entry_path(page_id).unlink(missing_ok=True)
