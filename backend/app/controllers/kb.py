"""KB upload / list / delete request handlers."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from fastapi import BackgroundTasks, HTTPException, UploadFile

from backend.services.knowledge_base import ingestion, store
from backend.shared.config import settings

logger = logging.getLogger(__name__)

# Tracks in-flight ingest jobs in this worker process (cleared on server reload).
_active_ingest_jobs: set[str] = set()


def _kb_dir() -> Path:
    return settings.KB_DIR


def _qdrant_path() -> str:
    return str(settings.KB_QDRANT_PATH)


def _pending_response(kb_id: str, source_name: str) -> dict:
    return {
        "id": kb_id,
        "name": source_name,
        "page_count": 0,
        "status": "processing",
    }


async def _run_ingest_job(kb_id: str, content: bytes, source_name: str) -> None:
    kb_dir = _kb_dir()
    _active_ingest_jobs.add(kb_id)
    try:
        if not store.kb_exists(kb_dir, kb_id):
            logger.info("KB ingest cancelled kb_id=%s (removed before start)", kb_id)
            return

        stats = await ingestion.ingest_pdf(content, source_name, kb_id, _qdrant_path())

        if not store.kb_exists(kb_dir, kb_id):
            logger.info("KB ingest aborted kb_id=%s (removed during ingest)", kb_id)
            return

        chunk_count = int(stats.get("chunk_count") or 0)
        if chunk_count == 0:
            store.update_kb_status(
                kb_dir,
                kb_id,
                status="failed",
                error="Could not extract any content from this PDF.",
                ingest_stats=stats,
            )
            return
        store.update_kb_status(
            kb_dir,
            kb_id,
            status="ready",
            page_count=int(stats.get("page_count") or 0),
            chunk_count=chunk_count,
            figure_count=int(stats.get("figure_count") or 0),
            ingest_stats=stats,
        )
        logger.info(
            "KB ingest complete kb_id=%s chunks=%d pages=%d figures=%d fallbacks=%d",
            kb_id,
            chunk_count,
            stats.get("page_count", 0),
            stats.get("figure_count", 0),
            stats.get("page_fallback_count", 0),
        )
    except Exception as exc:
        logger.exception("KB ingest failed kb_id=%s", kb_id)
        if store.kb_exists(kb_dir, kb_id):
            store.update_kb_status(kb_dir, kb_id, status="failed", error=str(exc))
    finally:
        _active_ingest_jobs.discard(kb_id)


async def handle_upload_kb(file: UploadFile, background_tasks: BackgroundTasks) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    kb_id = hashlib.sha256(content).hexdigest()[:16]
    source_name = file.filename
    qdrant_path = _qdrant_path()

    kb_dir = _kb_dir()
    existing = store.get_kb(kb_dir, kb_id)

    if store.kb_is_ready(kb_dir, kb_id, qdrant_path=qdrant_path):
        return existing or {
            "id": kb_id,
            "name": source_name,
            "page_count": 0,
            "status": "ready",
        }

    if (
        existing
        and existing.get("status") == "processing"
        and kb_id in _active_ingest_jobs
    ):
        return existing

    store.register_kb_pending(kb_dir, kb_id, source_name)
    background_tasks.add_task(_run_ingest_job, kb_id, content, source_name)

    return _pending_response(kb_id, source_name)


async def handle_kb_status(kb_id: str) -> dict:
    entry = store.get_kb(_kb_dir(), kb_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return entry


async def handle_list_kbs() -> list[dict]:
    return store.list_kbs(_kb_dir())


async def handle_delete_kb(kb_id: str) -> dict:
    if not store.kb_exists(_kb_dir(), kb_id):
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    ingestion.delete_collection(kb_id, _qdrant_path())
    store.remove_kb(_kb_dir(), kb_id)
    return {"ok": True, "id": kb_id}
