from .ecommerce import router as ecommerce_router
from .ecommerce_shim import router as _legacy_ecommerce_router  # noqa: F401

__all__ = ["ecommerce_router"]
