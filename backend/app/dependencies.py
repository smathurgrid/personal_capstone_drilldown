"""FastAPI dependency injection bindings."""

from backend.core.factory import ServiceFactory, get_service_factory
from backend.core.protocols import (
    ExplainerContextAnalysis,
    ExplainerPageStore,
    ExplainerPageWorkflow,
    ImageGenerator,
    ProductSearch,
)
from backend.repositories.history_repository import HistoryRepository
from backend.services.ecommerce.catalog_service import EcommerceCatalogService
from backend.services.ecommerce.identification_service import IdentificationService
from backend.services.ecommerce.search_service import SearchService
from backend.services.explainer.image_generator import MockImageGenerator, OllamaImageGenerator


def get_factory() -> ServiceFactory:
    return get_service_factory()


def get_image_generator() -> ImageGenerator:
    return get_factory().create_image_generator()


def get_product_identification_service() -> IdentificationService:
    return get_factory().create_identification_service()


def get_product_search_service() -> ProductSearch:
    return get_factory().create_search_service()


def get_history_repository() -> HistoryRepository:
    return get_factory().create_history_repository()


def get_explainer_page_store() -> ExplainerPageStore:
    return get_factory().create_explainer_page_store()


def get_explainer_context_analyzer() -> ExplainerContextAnalysis:
    return get_factory().create_explainer_context_analyzer()


def get_explainer_page_orchestrator() -> ExplainerPageWorkflow:
    return get_factory().create_explainer_page_orchestrator()


def get_ecommerce_catalog_service() -> EcommerceCatalogService:
    return get_factory().create_ecommerce_catalog_service()
