"""
DrillDown Unified API.

Mounts:
  /api/health
  /api/ecommerce/*
  /api/explainer/vision/*
  /api/explainer/generate/*
  /uploads, /dataset, /static
"""

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

UNIFIED_ROOT = Path(__file__).resolve().parents[2]
if str(UNIFIED_ROOT) not in sys.path:
    sys.path.insert(0, str(UNIFIED_ROOT))

from backend.app.routes import (  # noqa: E402
    ecommerce_router,
    generation_router,
    tools_router,
    vision_router,
)
from backend.agent.routes import router as agent_router
from backend.shared.config import ensure_data_dirs, settings
from backend.shared.errors import register_exception_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DrillDown Unified API",
    description="Ecommerce catalog + Explainer vision and generation",
    version="0.5.0-complete",
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ecommerce_router, prefix="/api/ecommerce")
app.include_router(vision_router, prefix="/api/explainer/vision")
app.include_router(generation_router, prefix="/api/explainer/generate")
app.include_router(tools_router, prefix="/api")
app.include_router(agent_router, prefix="/api/agent")

app.mount("/uploads", StaticFiles(directory=str(settings.UPLOADS_DIR)), name="uploads")
app.mount("/dataset", StaticFiles(directory=str(settings.DATASET_IMAGES_DIR)), name="dataset")
app.mount(
    "/static",
    StaticFiles(directory=str(settings.EXPLAINER_STATIC_DIR)),
    name="explainer-static",
)


@app.on_event("startup")
async def on_startup():
    ensure_data_dirs()
    logger.info("DrillDown unified API started (stage %s)", settings.STAGE)


@app.get("/")
async def root():
    return {
        "message": "DrillDown Unified API",
        "stage": settings.STAGE,
        "docs": "/docs",
        "health": "/api/health",
        "modes": {
            "ecommerce": "/api/ecommerce/health",
            "explainer_vision": "/api/explainer/vision/health",
            "explainer_generation": "/api/explainer/generate/health",
            "layer3_tools": "/api/analyze",
            "agent": "/api/agent/health",
        },
    }


@app.get("/api/health")
async def api_health():
    from backend.app.controllers.ecommerce import get_ecommerce_module_status
    from backend.app.controllers.generation import get_generation_module_status
    from backend.app.controllers.vision import get_vision_module_status

    return {
        "status": "ok",
        "stage": settings.STAGE,
        "modules": {
            "ecommerce": get_ecommerce_module_status(),
            "explainer_vision": get_vision_module_status(),
            "explainer_generate": get_generation_module_status(),
        },
    }
