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

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

UNIFIED_ROOT = Path(__file__).resolve().parents[2]
if str(UNIFIED_ROOT) not in sys.path:
    sys.path.insert(0, str(UNIFIED_ROOT))

from backend.app.routes import (  # noqa: E402
    ecommerce_router,
    generation_router,
    kb_router,
    tools_router,
    vision_router,
)
from backend.agent.routes import router as agent_router
from backend.auth.database import close_db, init_db
from backend.auth.dependencies import require_authenticated_api
from backend.auth.routes import router as auth_router
from backend.shared.config import ensure_data_dirs, settings
from backend.shared.errors import register_exception_handlers
from backend.shared.ollama_health import ollama_reachable

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
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

protected = [Depends(require_authenticated_api)]

app.include_router(auth_router)
app.include_router(ecommerce_router, prefix="/api/ecommerce", dependencies=protected)
app.include_router(vision_router, prefix="/api/explainer/vision", dependencies=protected)
app.include_router(generation_router, prefix="/api/explainer/generate", dependencies=protected)
app.include_router(tools_router, prefix="/api", dependencies=protected)
app.include_router(agent_router, prefix="/api/agent", dependencies=protected)
app.include_router(kb_router, prefix="/api/kb", dependencies=protected)

app.mount("/uploads", StaticFiles(directory=str(settings.UPLOADS_DIR)), name="uploads")
app.mount(
    "/profile-uploads",
    StaticFiles(directory=str(settings.PROFILE_UPLOADS_DIR)),
    name="profile-uploads",
)
app.mount("/dataset", StaticFiles(directory=str(settings.DATASET_IMAGES_DIR)), name="dataset")
app.mount(
    "/static",
    StaticFiles(directory=str(settings.EXPLAINER_STATIC_DIR)),
    name="explainer-static",
)


@app.on_event("startup")
async def on_startup():
    ensure_data_dirs()
    await init_db()
    from backend.services.explainer.pending_drill_store import prune_expired

    prune_expired()
    logger.info("DrillDown unified API started (stage %s)", settings.STAGE)
    if settings.MODEL_PROVIDER == "mock":
        logger.warning(
            "MODEL_PROVIDER=mock — image generation uses cropped placeholders, NOT %s. "
            "Set MODEL_PROVIDER=ollama in .env for real Flux output.",
            settings.IMAGE_MODEL,
        )
    elif not ollama_reachable():
        logger.warning(
            "Ollama is not reachable at %s — vision labeling and Flux generation will fail "
            "until you run: ollama serve",
            settings.OLLAMA_BASE,
        )


@app.on_event("shutdown")
async def on_shutdown():
    await close_db()


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
