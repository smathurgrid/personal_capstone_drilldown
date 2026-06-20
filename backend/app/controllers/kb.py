"""KB upload / list / delete request handlers."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import HTTPException, UploadFile

from backend.services.knowledge_base import ingestion, store
from backend.shared.config import settings


def _kb_dir() -> Path:
    return settings.KB_DIR


def _qdrant_path() -> str:
    return str(settings.KB_QDRANT_PATH)


async def handle_upload_kb(file: UploadFile) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    # Stable ID from content hash (re-uploading same PDF is idempotent)
    kb_id = hashlib.sha256(content).hexdigest()[:16]
    source_name = file.filename

    chunk_count = await ingestion.ingest_pdf(content, source_name, kb_id, _qdrant_path())
    if chunk_count == 0:
        raise HTTPException(status_code=422, detail="Could not extract any content from this PDF.")

    entry = store.register_kb(_kb_dir(), kb_id, source_name, chunk_count)
    return entry


async def handle_list_kbs() -> list[dict]:
    return store.list_kbs(_kb_dir())


async def handle_delete_kb(kb_id: str) -> dict:
    if not store.kb_exists(_kb_dir(), kb_id):
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    ingestion.delete_collection(kb_id, _qdrant_path())
    store.remove_kb(_kb_dir(), kb_id)
    return {"ok": True, "id": kb_id}
