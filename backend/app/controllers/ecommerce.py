"""Ecommerce request handlers."""

from fastapi import UploadFile

from backend.core.protocols import ProductSearch
from backend.services.ecommerce.catalog_service import EcommerceCatalogService
from backend.shared.config import settings


_search_service_cached = None
_search_service_error = None
_search_service_checked = False


def get_ecommerce_module_status(product_search: ProductSearch | None = None) -> dict:
    global _search_service_cached, _search_service_error, _search_service_checked

    from backend.app.dependencies import get_product_search_service

    qdrant_ready = settings.QDRANT_PATH.exists()
    dataset_ready = settings.DATASET_IMAGES_DIR.exists() and any(
        settings.DATASET_IMAGES_DIR.glob("*")
    )

    if not _search_service_checked:
        try:
            _search_service_cached = (product_search or get_product_search_service())
            _search_service_error = None
        except Exception as exc:
            _search_service_error = str(exc)
        _search_service_checked = True

    search_ok = _search_service_cached is not None
    search_err = _search_service_error

    return {
        "module": "ecommerce",
        "stage": settings.STAGE,
        "ready": qdrant_ready and dataset_ready and bool(settings.GOOGLE_API_KEY) and search_ok,
        "source": "ecommerce",
        "checks": {
            "qdrant_path_exists": qdrant_ready,
            "dataset_images_present": dataset_ready,
            "google_api_key_set": bool(settings.GOOGLE_API_KEY),
            "search_service_loaded": search_ok,
            "search_error": search_err,
            "uploads_dir": str(settings.UPLOADS_DIR),
        },
    }


async def handle_upload(file: UploadFile, catalog_service: EcommerceCatalogService):
    return await catalog_service.upload_image(file)


async def handle_identify(
    image_id: str, x: float, y: float, catalog_service: EcommerceCatalogService
):
    return await catalog_service.identify_item(image_id, x, y)


async def handle_drill(
    product_id: int, x: float, y: float, catalog_service: EcommerceCatalogService
):
    return await catalog_service.drill_down(product_id, x, y)


def handle_history(catalog_service: EcommerceCatalogService):
    return catalog_service.get_history()
