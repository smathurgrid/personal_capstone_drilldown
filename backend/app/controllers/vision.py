"""Explainer vision request handlers."""

import hashlib
import io

from fastapi import HTTPException, UploadFile
from PIL import Image

from backend.core.protocols import ExplainerContextAnalysis, ExplainerPageStore, ExplainerPageWorkflow
from backend.models.explainer import AnalyzeRequest, ConfirmDrillRequest, PageRequest
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
            "vision_model_layer3": settings.EXPLAINER_VISION_MODEL,
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
        cache_bust=req.cacheBust,
        kb_id=req.kbId or None,
    )


async def handle_analyze(
    req: AnalyzeRequest,
    page_store: ExplainerPageStore,
    context_analyzer: ExplainerContextAnalysis,
):
    image_path = page_store.page_image_path(req.pageId)
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    result = await context_analyzer.analyze_page(
        str(image_path),
        model_key=req.visionModel or "qwen3.5",
        scan_mode=req.scanMode or "global",
        depth=req.depth,
    )
    page_store.save_page_scan(
        req.pageId,
        metadata=result.get("metadata", {}),
        raw_json=result.get("rawJson", "{}"),
        vision_model=req.visionModel or "qwen3.5",
        scan_mode=req.scanMode or "global",
        depth=req.depth,
    )
    return result


async def handle_get_stored_page(page_id: str, orchestrator: ExplainerPageWorkflow):
    try:
        return orchestrator.get_page(page_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def handle_confirm_drill(req: ConfirmDrillRequest, orchestrator: ExplainerPageWorkflow):
    try:
        return await orchestrator.confirm_drill(req.pageId, req.drillTopic)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def handle_cancel_drill(page_id: str, orchestrator: ExplainerPageWorkflow):
    orchestrator.cancel_drill(page_id)
    return {"ok": True}


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
