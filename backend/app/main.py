"""Modular backend for Semantic Drill Down.

Endpoints:
 - GET  /api/health
 - POST /api/analyze
 - POST /api/generate
 - POST /api/generate-from-text

Configuration via .env:
 OLLAMA_BASE, VISION_MODEL, IMAGE_MODEL, MODEL_PROVIDER (ollama|mock)
"""
import logging
import sys
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Allow this module to be started either from the repo root
# (`uvicorn backend.app.main:app`) or from `backend/` (`uvicorn app.main:app`).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.services.factory import get_vision_service, get_image_service
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Semantic Drill Down API")

# CORS - allow Vite dev server and any origin for simplicity
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate services once at startup
vision_service = get_vision_service()
image_service = get_image_service()


@app.get("/api/health")
def health():
    """Health check – reports configured models."""
    ollama_ok = settings.MODEL_PROVIDER == "mock"
    if settings.MODEL_PROVIDER == "ollama":
        try:
            resp = requests.get(f"{settings.OLLAMA_BASE}/api/tags", timeout=2)
            ollama_ok = resp.ok
        except requests.RequestException:
            ollama_ok = False

    return {
        "status": "ok",
        "ollama": ollama_ok,
        "vision_model": settings.VISION_MODEL,
        "image_model": settings.IMAGE_MODEL,
        "provider": settings.MODEL_PROVIDER,
    }


@app.post("/api/analyze")
async def analyze(
    image: UploadFile = File(...),
    x: int = Form(...),
    y: int = Form(...),
    radius: int = Form(80),
):
    """Analyze a region – returns analysis text, prompt, and base64 crops."""
    try:
        logger.info("/api/analyze called: x=%s y=%s radius=%s filename=%s",
                    x, y, radius, getattr(image, 'filename', None))
        img_bytes = await image.read()
        result = await vision_service.analyze(img_bytes, x, y, radius)
        return result
    except Exception as exc:
        logger.exception("/api/analyze error")
        return JSONResponse(
            {"error": "analyze failed", "detail": str(exc)},
            status_code=500,
        )


@app.post("/api/generate")
async def generate(request: Request):
    """Generate a drill‑down image from prompt and crops."""
    try:
        body = await request.json()
        prompt = body.get("prompt", "")
        local_crop_b64 = body.get("local_crop_b64")
        global_b64 = body.get("global_b64")

        if not local_crop_b64:
            return JSONResponse(
                {"error": "local_crop_b64 required"},
                status_code=400,
            )

        logger.info("/api/generate called (prompt len=%d)", len(prompt))
        result = await image_service.generate(prompt, local_crop_b64, global_b64)
        return result
    except Exception as exc:
        logger.exception("/api/generate error")
        return JSONResponse(
            {"error": "generate failed", "detail": str(exc)},
            status_code=500,
        )


@app.post("/api/generate-from-text")
async def generate_from_text(request: Request):
    """Create an initial overview image from a text topic."""
    try:
        body = await request.json()
        topic_value = body.get("topic", "Generated Topic")
        topic = str(topic_value).strip() or "Generated Topic"
        logger.info("/api/generate-from-text called: topic=%s", topic)

        illustration_prompt = (
            f"A clean educational technical illustration of {topic}. "
            "Show the important internal structures and layers as a rich visual explainer, "
            "with cross-section or cutaway details where useful. Use a polished textbook "
            "illustration style with a muted, natural color palette. Do not include any "
            "text, labels, titles, annotations, callout lines, numbers, symbols, or lettering."
        )

        gen_result = await image_service.generate(
            prompt=illustration_prompt,
            local_crop_b64=None,
            global_b64=None,
        )
        return {
            "image_b64": gen_result["image_b64"],
            "image_prompt": illustration_prompt,
        }
    except Exception as exc:
        logger.exception("/api/generate-from-text error")
        return JSONResponse(
            {"error": "generate-from-text failed", "detail": str(exc)},
            status_code=500,
        )
