"""Explainer vision API routes."""

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse

from backend.app.controllers import vision as vision_controller
from backend.app.dependencies import (
    get_explainer_context_analyzer,
    get_explainer_page_orchestrator,
    get_explainer_page_store,
)
from backend.core.protocols import (
    ExplainerContextAnalysis,
    ExplainerPageStore,
    ExplainerPageWorkflow,
)
from backend.models.explainer import AnalyzeRequest, PageRequest
from backend.shared.health import register_module_health

router = APIRouter(tags=["explainer-vision"])

register_module_health(router, vision_controller.get_vision_module_status)


@router.post("/stream-page")
async def stream_page(
    req: PageRequest,
    orchestrator: ExplainerPageWorkflow = Depends(get_explainer_page_orchestrator),
):
    return StreamingResponse(
        vision_controller.handle_stream_page(req, orchestrator),
        media_type="text/event-stream",
    )


@router.post("/analyze")
async def analyze_page(
    req: AnalyzeRequest,
    page_store: ExplainerPageStore = Depends(get_explainer_page_store),
    context_analyzer: ExplainerContextAnalysis = Depends(get_explainer_context_analyzer),
):
    return await vision_controller.handle_analyze(req, page_store, context_analyzer)


@router.post("/page")
async def get_page(
    req: PageRequest,
    orchestrator: ExplainerPageWorkflow = Depends(get_explainer_page_orchestrator),
):
    return await vision_controller.handle_get_page(req, orchestrator)


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    page_store: ExplainerPageStore = Depends(get_explainer_page_store),
):
    return await vision_controller.handle_upload(file, page_store)
