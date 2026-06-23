"""Per-session JSONL trace of pi-agent tool calls and decision reasoning.

Writes one JSON object per line to ``<AGENT_LOG_DIR>/<session_id>.jsonl`` so an
auto-drill run can be inspected or replayed afterwards. Captures both *what* the
agent did (tool name, params, result summary, timing) and *why* (the model's
thinking / text emitted before each tool call).

Base64 image blobs are elided — they bloat the log and aren't useful for tracing.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from backend.shared.config import settings

logger = logging.getLogger(__name__)

# Result/param values longer than this are truncated in the trace.
_MAX_VALUE_CHARS = 800
# Keys whose values look like base64 image data and should never be written raw.
_ELIDE_KEYS = ("image_b64", "local_crop_b64", "global_b64", "parent_image_b64")


def _scrub(value: Any) -> Any:
    """Recursively elide base64 blobs and truncate long strings for logging."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if k in _ELIDE_KEYS and isinstance(v, str):
                out[k] = f"<elided {len(v)} chars>"
            else:
                out[k] = _scrub(v)
        return out
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    if isinstance(value, str) and len(value) > _MAX_VALUE_CHARS:
        return value[:_MAX_VALUE_CHARS] + f"... <+{len(value) - _MAX_VALUE_CHARS} chars>"
    return value


def _result_summary(result: Any) -> Any:
    """Pull a compact summary out of a pi-agent tool result dict."""
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            texts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            if texts:
                joined = "\n".join(texts)
                try:
                    return _scrub(json.loads(joined))
                except (ValueError, TypeError):
                    return _scrub(joined)
    return _scrub(result)


class AgentTraceLogger:
    """Append-only JSONL writer for a single agent session."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._start_ts: dict[str, float] = {}
        log_dir = settings.AGENT_LOG_DIR
        log_dir.mkdir(parents=True, exist_ok=True)
        self.path = log_dir / f"{session_id}.jsonl"
        self._fh = self.path.open("a", encoding="utf-8")
        logger.info("Agent trace → %s", self.path)

    def _write(self, event: str, payload: dict[str, Any]) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "event": event,
            **payload,
        }
        self._fh.write(json.dumps(record, default=str) + "\n")
        self._fh.flush()

    # -- tool lifecycle (driven by pi-agent hooks) ------------------------

    def tool_start(self, tool_id: str, name: str, params: dict) -> None:
        self._start_ts[tool_id] = time.monotonic()
        self._write("tool_start", {"tool_id": tool_id, "tool": name, "params": _scrub(params)})
        logger.info("[agent %s] → %s(%s)", self.session_id, name, _scrub(params))

    def tool_end(self, tool_id: str, name: str, result: Any, is_error: bool) -> None:
        started = self._start_ts.pop(tool_id, None)
        elapsed_ms = round((time.monotonic() - started) * 1000, 1) if started else None
        self._write(
            "tool_end",
            {
                "tool_id": tool_id,
                "tool": name,
                "is_error": is_error,
                "elapsed_ms": elapsed_ms,
                "result": _result_summary(result),
            },
        )
        logger.info(
            "[agent %s] ← %s (%sms%s)",
            self.session_id,
            name,
            elapsed_ms,
            ", error" if is_error else "",
        )

    # -- model reasoning (driven by the event-stream tap) -----------------

    def reasoning(self, text: str, kind: str = "text") -> None:
        text = text.strip()
        if text:
            self._write("reasoning", {"kind": kind, "text": _scrub(text)})

    def turn_end(self, stop_reason: str | None) -> None:
        self._write("turn_end", {"stop_reason": stop_reason})

    def agent_event(self, name: str, payload: dict | None = None) -> None:
        self._write(name, payload or {})

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()
