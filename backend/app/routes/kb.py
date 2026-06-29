"""Knowledge base API routes."""

from fastapi import APIRouter, BackgroundTasks, File, UploadFile

from backend.app.controllers import kb as kb_controller

router = APIRouter(tags=["knowledge-base"])


@router.post("/upload")
async def upload_kb(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload a PDF and ingest it into the knowledge base (background job)."""
    return await kb_controller.handle_upload_kb(file, background_tasks)


@router.get("/status/{kb_id}")
async def kb_status(kb_id: str):
    """Poll ingestion status for a knowledge base."""
    return await kb_controller.handle_kb_status(kb_id)


@router.get("/list")
async def list_kbs():
    """List all uploaded knowledge bases."""
    return await kb_controller.handle_list_kbs()


@router.delete("/{kb_id}")
async def delete_kb(kb_id: str):
    """Delete a knowledge base and its Qdrant collection."""
    return await kb_controller.handle_delete_kb(kb_id)
