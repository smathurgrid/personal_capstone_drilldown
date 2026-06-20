"""Knowledge base API routes."""

from fastapi import APIRouter, File, UploadFile

from backend.app.controllers import kb as kb_controller

router = APIRouter(tags=["knowledge-base"])


@router.post("/upload")
async def upload_kb(file: UploadFile = File(...)):
    """Upload a PDF and ingest it into the knowledge base."""
    return await kb_controller.handle_upload_kb(file)


@router.get("/list")
async def list_kbs():
    """List all uploaded knowledge bases."""
    return await kb_controller.handle_list_kbs()


@router.delete("/{kb_id}")
async def delete_kb(kb_id: str):
    """Delete a knowledge base and its Qdrant collection."""
    return await kb_controller.handle_delete_kb(kb_id)
