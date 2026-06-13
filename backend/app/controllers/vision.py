"""Explainer vision request handlers."""

import hashlib
import io

from fastapi import HTTPException, UploadFile
from PIL import Image

from backend.core.protocols import ExplainerContextAnalysis, ExplainerPageStore, ExplainerPageWorkflow
from backend.models.explainer import AnalyzeRequest, PageRequest
from backend.shared.config import settings
from backend.shared.grounding_defaults import default_grounding_mode, sam2_available


def get_vision_module_status() -> dict:
    static_ready = settings.EXPLAINER_STATIC_DIR.exists()
    return {
        "module": "explainer-vision",
        "stage": settings.STAGE,
        "ready": static_ready,
        "source": "explainer-vision",
        "checks": {
            "static_dir": str(settings.EXPLAINER_STATIC_DIR),
            "static_dir_exists": static_ready,
            "vision_model": settings.EXPLAINER_VISION_MODEL,
            "ollama_base": settings.OLLAMA_BASE,
            "llm_provider": settings.LLM_PROVIDER,
            "vision_model_layer3": settings.VISION_MODEL,
            "sam2_configured": bool(settings.SAM2_PATH),
            "sam2_available": sam2_available(),
            "default_grounding_mode": default_grounding_mode(),
        },
        "message": "Vision labeling via Ollama; generation handled by explainer-generation module",
    }


def handle_stream_page(req: PageRequest, orchestrator: ExplainerPageWorkflow):
    return orchestrator.stream_page(
        query=req.query,
        parent_id=req.parentId,
        x=req.x,
        y=req.y,
        vision_model=req.visionModel or "qwen3.5",
        grounding_mode=req.groundingMode or default_grounding_mode(),
        custom_topic=req.customTopic,
    )


async def handle_analyze(
    req: AnalyzeRequest,
    page_store: ExplainerPageStore,
    context_analyzer: ExplainerContextAnalysis,
):
    image_path = page_store.page_image_path(req.pageId)
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return await context_analyzer.analyze_page(str(image_path), model_key=req.visionModel or "qwen3.5")


async def handle_get_page(req: PageRequest, orchestrator: ExplainerPageWorkflow):
    try:
        return await orchestrator.get_or_create_page(
            query=req.query,
            parent_id=req.parentId,
            x=req.x,
            y=req.y,
            vision_model=req.visionModel or "qwen3.5",
            grounding_mode=req.groundingMode or default_grounding_mode(),
            custom_topic=req.customTopic,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def handle_upload(file: UploadFile, page_store: ExplainerPageStore):
    content = await file.read()
    page_id = hashlib.sha256(content).hexdigest()
    file_path = page_store.page_image_path(page_id)
    image = Image.open(io.BytesIO(content))
    if image.mode != "RGB":
        image = image.convert("RGB")
    image.save(file_path, "PNG")
    return {
        "id": page_id,
        "imageUrl": page_store.image_url(page_id),
        "metadata": {},
        "rawJson": "",
        "inputPrompt": "",
        "samConfidence": None,
    }
