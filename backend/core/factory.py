"""Injectable service factory — replaces module-level singleton getters."""

from backend.repositories.history_repository import HistoryRepository
from backend.repositories.page_repository import PageRepository
from backend.services.ecommerce.catalog_service import EcommerceCatalogService
from backend.services.ecommerce.drill_coordinator import DrillCoordinator
from backend.services.ecommerce.identification_service import IdentificationService
from backend.services.ecommerce.search_service import SearchService
from backend.services.explainer.context_analyzer import ContextAnalyzer
from backend.services.explainer.drill_analyzer import DrillAnalyzer
from backend.services.explainer.drill_context_resolver import DrillContextResolver
from backend.services.explainer.grounding_service import GroundingService
from backend.services.explainer.page_orchestrator import PageOrchestrator
from backend.services.explainer.image_generator import MockImageGenerator, OllamaImageGenerator
from backend.services.explainer.image_worker_pool import PooledImageGenerator, probe_live_workers
from backend.repositories.session_repository import SessionRepository
from backend.shared.config import Settings, settings
import logging

logger = logging.getLogger(__name__)


class ServiceFactory:
    """Creates and caches application services for the current process."""

    def __init__(self, app_settings: Settings | None = None) -> None:
        self._settings = app_settings or settings
        self._image_generator = None
        self._product_identification: IdentificationService | None = None
        self._product_search: SearchService | None = None
        self._drill_coordinator: DrillCoordinator | None = None
        self._drill_history: HistoryRepository | None = None
        self._explainer_page_store: PageRepository | None = None
        self._explainer_context_analyzer: ContextAnalyzer | None = None
        self._explainer_drill_analyzer: DrillAnalyzer | None = None
        self._explainer_grounding: GroundingService | None = None
        self._explainer_drill_context: DrillContextResolver | None = None
        self._explainer_page_orchestrator: PageOrchestrator | None = None
        self._ecommerce_catalog: EcommerceCatalogService | None = None

    def create_image_generator(self):
        if self._image_generator is None:
            if self._settings.MODEL_PROVIDER == "mock":
                self._image_generator = MockImageGenerator()
            elif self._settings.IMAGE_BACKEND == "pool" or len(self._settings.IMAGE_OLLAMA_BASES) > 1:
                # Speculative drill: distribute hotspot images across worker Macs.
                # Wire in ALL configured workers (not just the ones up right now) so a
                # worker that comes online LATER is picked up automatically — the pool
                # health-checks each worker per request and falls back to the main Mac
                # when none are reachable. The probe below is just a startup log.
                urls = self._settings.IMAGE_OLLAMA_BASES
                live = probe_live_workers(urls)
                if live:
                    logger.info("image pool: %d/%d worker(s) live at startup -> %s", len(live), len(urls), live)
                else:
                    logger.warning(
                        "image pool: no workers live at startup %s — using main Mac until one comes online",
                        urls,
                    )
                self._image_generator = PooledImageGenerator(urls)
            else:
                self._image_generator = OllamaImageGenerator()
        return self._image_generator

    def create_main_image_generator(self):
        """Generator for the parent + free-click child images — stays on the MAIN
        Mac (local Ollama) so the worker pool is dedicated to hotspot prefetch."""
        if self._settings.MODEL_PROVIDER == "mock":
            return self.create_image_generator()
        return OllamaImageGenerator()

    def create_drill_session_store(self) -> SessionRepository:
        if getattr(self, "_drill_session_store", None) is None:
            self._drill_session_store = SessionRepository(self._settings.DRILL_SESSIONS_DB)
        return self._drill_session_store

    def create_identification_service(self) -> IdentificationService:
        if self._product_identification is None:
            self._product_identification = IdentificationService(self._settings)
        return self._product_identification

    def create_search_service(self) -> SearchService:
        if self._product_search is None:
            self._product_search = SearchService(self._settings)
        return self._product_search

    def create_drill_coordinator(self) -> DrillCoordinator:
        if self._drill_coordinator is None:
            self._drill_coordinator = DrillCoordinator(
                self.create_identification_service(),
                self.create_search_service(),
            )
        return self._drill_coordinator

    def create_history_repository(self) -> HistoryRepository:
        if self._drill_history is None:
            self._drill_history = HistoryRepository()
        return self._drill_history

    def create_explainer_page_store(self) -> PageRepository:
        if self._explainer_page_store is None:
            self._explainer_page_store = PageRepository(
                self._settings.EXPLAINER_STATIC_DIR
            )
        return self._explainer_page_store

    def create_explainer_context_analyzer(self) -> ContextAnalyzer:
        if self._explainer_context_analyzer is None:
            self._explainer_context_analyzer = ContextAnalyzer(self._settings)
        return self._explainer_context_analyzer

    def create_explainer_grounding_service(self) -> GroundingService:
        if self._explainer_grounding is None:
            self._explainer_grounding = GroundingService(
                self.create_explainer_page_store()
            )
        return self._explainer_grounding

    def create_explainer_drill_analyzer(self) -> DrillAnalyzer:
        if self._explainer_drill_analyzer is None:
            self._explainer_drill_analyzer = DrillAnalyzer(self._settings)
        return self._explainer_drill_analyzer

    def create_explainer_drill_context_resolver(self) -> DrillContextResolver:
        if self._explainer_drill_context is None:
            self._explainer_drill_context = DrillContextResolver(
                self.create_explainer_context_analyzer(),
                self.create_explainer_drill_analyzer(),
            )
        return self._explainer_drill_context

    def create_explainer_page_orchestrator(self) -> PageOrchestrator:
        if self._explainer_page_orchestrator is None:
            self._explainer_page_orchestrator = PageOrchestrator(
                page_store=self.create_explainer_page_store(),
                grounding_service=self.create_explainer_grounding_service(),
                drill_context_resolver=self.create_explainer_drill_context_resolver(),
                image_generator=self.create_image_generator(),
            )
        return self._explainer_page_orchestrator

    def create_ecommerce_catalog_service(self) -> EcommerceCatalogService:
        if self._ecommerce_catalog is None:
            self._ecommerce_catalog = EcommerceCatalogService(
                drill_coordinator=self.create_drill_coordinator(),
                drill_history=self.create_history_repository(),
            )
        return self._ecommerce_catalog


_factory: ServiceFactory | None = None


def get_service_factory() -> ServiceFactory:
    global _factory
    if _factory is None:
        _factory = ServiceFactory()
    return _factory


def reset_service_factory() -> None:
    global _factory
    _factory = None
