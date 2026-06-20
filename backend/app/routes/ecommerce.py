"""Ecommerce API routes."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from backend.app.controllers import ecommerce as ecommerce_controller
from backend.app.dependencies import get_ecommerce_catalog_service
from backend.services.ecommerce.catalog_service import EcommerceCatalogService
from backend.shared.health import register_module_health

router = APIRouter(tags=["ecommerce"])

register_module_health(router, ecommerce_controller.get_ecommerce_module_status)


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    catalog_service: EcommerceCatalogService = Depends(get_ecommerce_catalog_service),
):
    return await ecommerce_controller.handle_upload(file, catalog_service)


@router.post("/identify")
async def identify_item(
    imageId: str = Form(...),
    x: float = Form(...),
    y: float = Form(...),
    catalog_service: EcommerceCatalogService = Depends(get_ecommerce_catalog_service),
):
    return await ecommerce_controller.handle_identify(imageId, x, y, catalog_service)


@router.post("/drill")
async def drill_down(
    productId: int = Form(...),
    x: float = Form(...),
    y: float = Form(...),
    catalog_service: EcommerceCatalogService = Depends(get_ecommerce_catalog_service),
):
    return await ecommerce_controller.handle_drill(productId, x, y, catalog_service)


@router.get("/history")
async def get_history(
    catalog_service: EcommerceCatalogService = Depends(get_ecommerce_catalog_service),
):
    return ecommerce_controller.handle_history(catalog_service)
