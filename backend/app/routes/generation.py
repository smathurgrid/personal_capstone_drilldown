"""Explainer generation API routes."""

from fastapi import APIRouter, Depends, Request

from backend.app.controllers import generation as generation_controller
from backend.app.dependencies import get_image_generator
from backend.core.protocols import ImageGenerator
from backend.shared.health import register_module_health

router = APIRouter(tags=["explainer-generation"])

register_module_health(router, generation_controller.get_generation_module_status)


@router.post("/generate")
async def generate(
    request: Request,
    image_generator: ImageGenerator = Depends(get_image_generator),
):
    body = await request.json()
    return await generation_controller.handle_generate(body, image_generator)


@router.post("/generate-from-text")
async def generate_from_text_route(
    request: Request,
    image_generator: ImageGenerator = Depends(get_image_generator),
):
    body = await request.json()
    return await generation_controller.handle_generate_from_text(body, image_generator)
