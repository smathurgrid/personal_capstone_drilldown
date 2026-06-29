"""SQLite persistence for completed speculative-drill sessions.

In-flight sessions live in memory (the speculative engine keeps the 5 prefetched
branches per depth cached for instant clicks). When a session ends, its full
speculative tree — every ranked branch at every depth, with the chosen path
flagged and the generated images — is flushed here for durable storage.

Uses stdlib sqlite3 only (no extra dependencies). Images are stored as BLOBs.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    topic       TEXT,
    max_depth   INTEGER,
    final_depth INTEGER,
    created_at  TEXT,
    ended_at    TEXT
);

CREATE TABLE IF NOT EXISTS branches (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    depth        INTEGER NOT NULL,
    hotspot_id   TEXT NOT NULL,
    rank         INTEGER,
    x            REAL,
    y            REAL,
    label        TEXT,
    chosen       INTEGER NOT NULL DEFAULT 0,
    status       TEXT,
    analysis     TEXT,
    image_prompt TEXT,
    image        BLOB,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_branches_session ON branches(session_id, depth);
"""


class SessionRepository:
    """Durable store for finished drill sessions (SQLite)."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False + a lock: image generation runs in executor
        # threads, so flushes may arrive off the main loop thread.
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._lock = threading.Lock()

    def save_session(self, session: dict[str, Any]) -> None:
        """Persist one completed session and all its branches in a single txn.

        Expected shape:
          {
            "session_id", "topic", "max_depth", "final_depth",
            "created_at", "ended_at",
            "branches": [
              {"depth", "hotspot_id", "rank", "x", "y", "label",
               "chosen", "status", "analysis", "image_prompt", "image_b64"},
              ...
            ],
          }
        """
        branches = session.get("branches", [])
        with self._lock, self._conn:  # context-manager commits / rolls back
            self._conn.execute(
                """INSERT OR REPLACE INTO sessions
                   (session_id, topic, max_depth, final_depth, created_at, ended_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    session["session_id"],
                    session.get("topic"),
                    session.get("max_depth"),
                    session.get("final_depth"),
                    session.get("created_at"),
                    session.get("ended_at"),
                ),
            )
            # Replace any prior rows for this session (idempotent re-flush).
            self._conn.execute(
                "DELETE FROM branches WHERE session_id = ?", (session["session_id"],)
            )
            self._conn.executemany(
                """INSERT INTO branches
                   (session_id, depth, hotspot_id, rank, x, y, label,
                    chosen, status, analysis, image_prompt, image)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        session["session_id"],
                        b.get("depth"),
                        b.get("hotspot_id"),
                        b.get("rank"),
                        b.get("x"),
                        b.get("y"),
                        b.get("label"),
                        1 if b.get("chosen") else 0,
                        b.get("status"),
                        b.get("analysis"),
                        b.get("image_prompt"),
                        _b64_to_blob(b.get("image_b64")),
                    )
                    for b in branches
                ],
            )

    def load_session(self, session_id: str, *, include_images: bool = False) -> dict | None:
        """Read a session back (images optional to keep payloads light)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT session_id, topic, max_depth, final_depth, created_at, ended_at "
                "FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            cols = "depth, hotspot_id, rank, x, y, label, chosen, status, analysis, image_prompt"
            if include_images:
                cols += ", image"
            branch_rows = self._conn.execute(
                f"SELECT {cols} FROM branches WHERE session_id = ? ORDER BY depth, rank",
                (session_id,),
            ).fetchall()

        session = {
            "session_id": row[0],
            "topic": row[1],
            "max_depth": row[2],
            "final_depth": row[3],
            "created_at": row[4],
            "ended_at": row[5],
            "branches": [],
        }
        for br in branch_rows:
            entry = {
                "depth": br[0],
                "hotspot_id": br[1],
                "rank": br[2],
                "x": br[3],
                "y": br[4],
                "label": br[5],
                "chosen": bool(br[6]),
                "status": br[7],
                "analysis": br[8],
                "image_prompt": br[9],
            }
            if include_images:
                entry["image_b64"] = _blob_to_b64(br[10])
            session["branches"].append(entry)
        return session

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def _b64_to_blob(image_b64: str | None) -> bytes | None:
    if not image_b64:
        return None
    import base64

    try:
        return base64.b64decode(image_b64)
    except (ValueError, TypeError):
        return None


def _blob_to_b64(blob: bytes | None) -> str | None:
    if not blob:
        return None
    import base64

    return base64.b64encode(blob).decode("utf-8")
