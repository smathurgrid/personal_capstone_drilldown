from .ecommerce import router as ecommerce_router
from .generation import router as generation_router
from .kb import router as kb_router
from .tools import router as tools_router
from .vision import router as vision_router

__all__ = [
    "ecommerce_router",
    "vision_router",
    "generation_router",
    "tools_router",
    "kb_router",
]
