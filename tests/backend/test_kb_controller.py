"""KB upload controller — ingest job tracking and stale restart."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, UploadFile

from backend.app.controllers import kb as kb_controller
from backend.services.knowledge_base import store


@pytest.fixture
def kb_env(tmp_path, monkeypatch):
    monkeypatch.setattr(kb_controller.settings, "KB_DIR", tmp_path)
    monkeypatch.setattr(kb_controller.settings, "KB_QDRANT_PATH", tmp_path / "qdrant")
    kb_controller._active_ingest_jobs.clear()
    return tmp_path


def _upload_file(content: bytes, name: str = "manual.pdf") -> UploadFile:
    file = MagicMock(spec=UploadFile)
    file.filename = name
    file.read = AsyncMock(return_value=content)
    return file


def test_upload_returns_existing_when_ingest_active(kb_env):
    content = b"same-pdf-bytes-for-test"
    import hashlib

    kb_id = hashlib.sha256(content).hexdigest()[:16]
    store.register_kb_pending(kb_env, kb_id, "manual.pdf")
    kb_controller._active_ingest_jobs.add(kb_id)

    tasks = BackgroundTasks()
    with patch("backend.app.controllers.kb.store.kb_is_ready", return_value=False):
        result = asyncio.run(kb_controller.handle_upload_kb(_upload_file(content), tasks))

    assert result["status"] == "processing"
    assert result["id"] == kb_id
    assert len(tasks.tasks) == 0


def test_upload_restarts_stale_processing_job(kb_env):
    content = b"restart-me-pdf-content"
    kb_id = "a" * 16
    store.register_kb_pending(kb_env, kb_id, "manual.pdf")

    tasks = BackgroundTasks()
    with (
        patch("backend.app.controllers.kb.hashlib.sha256") as sha,
        patch("backend.app.controllers.kb.store.kb_is_ready", return_value=False),
        patch.object(kb_controller, "_run_ingest_job", new_callable=AsyncMock),
    ):
        sha.return_value.hexdigest.return_value = kb_id
        result = asyncio.run(kb_controller.handle_upload_kb(_upload_file(content), tasks))

    assert result["status"] == "processing"
    assert len(tasks.tasks) == 1


def test_ingest_job_skips_status_update_when_deleted(kb_env):
    content = b"pdf"
    kb_id = "kb-to-delete"
    store.register_kb_pending(kb_env, kb_id, "manual.pdf")

    async def fake_ingest(*_args, **_kwargs):
        store.remove_kb(kb_env, kb_id)
        return {"chunk_count": 5, "page_count": 2, "figure_count": 1, "page_fallback_count": 0}

    with patch("backend.app.controllers.kb.ingestion.ingest_pdf", side_effect=fake_ingest):
        asyncio.run(kb_controller._run_ingest_job(kb_id, content, "manual.pdf"))

    assert store.get_kb(kb_env, kb_id) is None
