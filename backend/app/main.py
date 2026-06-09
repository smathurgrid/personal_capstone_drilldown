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
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import settings
from ..services.factory import get_vision_service, get_image_service

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
    return {
        "status": "ok",
        "ollama": True,
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
        topic = body.get("topic", "Generated Topic")
        logger.info("/api/generate-from-text called: topic=%s", topic)

        # 1️⃣ Use vision service to craft a detailed illustration prompt
        # We need a dummy image to feed the vision service – use a blank image.
        from PIL import Image
        import io
        blank = Image.new("RGB", (512, 512), color=(255, 255, 255))
        buf = io.BytesIO()
        blank.save(buf, format="PNG")
        blank_bytes = buf.getvalue()

        # The vision service expects coordinates; we can pass center.
        vision_result = await vision_service.analyze(
            blank_bytes,
            x=256,
            y=256,
            radius=200,  # covers most of the blank image
        )
        # The vision service returns an image_prompt we can reuse.
        illustration_prompt = vision_result.get("image_prompt", "")
        if not illustration_prompt:
            # fallback: construct a simple prompt
            illustration_prompt = f"A clean technical illustration of {topic}, no text."

        # 2️⃣ Generate the image with the image service
        # For text‑to‑image we don't have crops; we reuse the blank image as both crops.
        blank_b64 = (
            base64.b64encode(blank_bytes).decode()
        )  # reuse same blank for local and global
        gen_result = await image_service.generate(
            prompt=illustration_prompt,
            local_crop_b64=blank_b64,
            global_b64=blank_b64,
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
