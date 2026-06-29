"""Canonical Layer 3 tool routes (architecture doc contracts)."""

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from backend.app.controllers import tools as tools_controller
from backend.app.dependencies import get_image_generator
from backend.core.protocols import ImageGenerator

router = APIRouter(tags=["layer3-tools"])


@router.post("/analyze")
async def analyze_click(
    image: UploadFile = File(...),
    x: float = Form(...),
    y: float = Form(...),
    radius: float = Form(80),
):
    """Per-click analyze: FormData image + pixel (x,y) → ANALYSIS + IMAGE_PROMPT."""
    return await tools_controller.handle_analyze_click(image, x, y, radius)


@router.post("/analyze-b64")
async def analyze_b64(request: Request):
    """Agent/human JSON variant: base64 image + normalized (x,y)."""
    body = await request.json()
    return await tools_controller.handle_analyze_b64(body)


@router.post("/pick-next-region")
async def pick_next_region(request: Request):
    """VLM selects next drill coordinate on parent image."""
    body = await request.json()
    return await tools_controller.handle_pick_next_region(body)


@router.post("/generate")
async def generate(
    request: Request,
    image_generator: ImageGenerator = Depends(get_image_generator),
):
    body = await request.json()
    return await tools_controller.handle_generate(body, image_generator)


@router.post("/generate-from-text")
async def generate_from_text_route(
    request: Request,
    image_generator: ImageGenerator = Depends(get_image_generator),
):
    body = await request.json()
    return await tools_controller.handle_generate_from_text(body, image_generator)
