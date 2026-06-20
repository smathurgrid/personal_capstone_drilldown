"""Service factory dependency injection tests."""

from backend.core.factory import ServiceFactory, reset_service_factory


def test_factory_returns_same_lazy_singleton_per_service() -> None:
    reset_service_factory()
    factory = ServiceFactory()
    first = factory.create_image_generator()
    second = factory.create_image_generator()
    assert first is second


def test_factory_reset_creates_new_instances() -> None:
    reset_service_factory()
    factory = ServiceFactory()
    first = factory.create_history_repository()
    reset_service_factory()
    second = ServiceFactory().create_history_repository()
    assert first is not second
