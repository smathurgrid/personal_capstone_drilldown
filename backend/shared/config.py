"""Unified application settings loaded from environment / .env."""

from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Application root — all paths resolve relative to drilldown-unified/
APP_ROOT = Path(__file__).resolve().parents[2]

if load_dotenv:
    load_dotenv(APP_ROOT / ".env")

# Back-compat alias used by a few modules
UNIFIED_ROOT = APP_ROOT


def _path(value: str | None, default: str) -> Path:
    raw = value or default
    path = Path(raw)
    if not path.is_absolute():
        path = UNIFIED_ROOT / path
    return path


class Settings:
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # Ecommerce (Bhavya — Stage 2)
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    QDRANT_PATH: Path = _path(os.getenv("QDRANT_PATH"), "data/qdrant_storage")
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "fashion_products")
    UPLOADS_DIR: Path = _path(os.getenv("UPLOADS_DIR"), "data/ecommerce/uploads")
    DEBUG_DIR: Path = _path(os.getenv("DEBUG_DIR"), "data/ecommerce/debug")
    DATASET_IMAGES_DIR: Path = _path(
        os.getenv("DATASET_IMAGES_DIR"), "data/fashion-dataset/images"
    )

    # Explainer vision (Rohith — Stage 2)
    EXPLAINER_STATIC_DIR: Path = _path(
        os.getenv("EXPLAINER_STATIC_DIR"), "data/explainer/static"
    )
    HF_TOKEN: str = os.getenv("HF_TOKEN", "")
    EXPLAINER_VISION_MODEL: str = os.getenv(
        "EXPLAINER_VISION_MODEL",
        os.getenv("ROHITH_VISION_MODEL", "qwen3.5:9b"),
    )

    # Explainer generation (Sid — Stage 2)
    OLLAMA_BASE: str = os.getenv("OLLAMA_BASE", "http://localhost:11434")
    IMAGE_MODEL: str = os.getenv("IMAGE_MODEL", "x/flux2-klein:4b-bf16")
    VISION_MODEL: str = os.getenv("VISION_MODEL", "qwen2.5vl:7b")
    MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "ollama").lower()
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama").lower()
    LITELLM_PROXY_BASE: str = os.getenv("LITELLM_PROXY_BASE", "http://localhost:4000")
    LITELLM_API_KEY: str = os.getenv("LITELLM_API_KEY", "")
    AGENT_ORCHESTRATOR_MODEL: str = os.getenv("AGENT_ORCHESTRATOR_MODEL", "llama3.1")

    SAM2_PATH: str = os.getenv("SAM2_PATH", "")
    DEFAULT_GROUNDING_MODE: str = os.getenv("DEFAULT_GROUNDING_MODE", "")

    # Knowledge Base (RAG)
    KB_DIR: Path = _path(os.getenv("KB_DIR"), "data/kb")
    KB_QDRANT_PATH: Path = _path(os.getenv("KB_QDRANT_PATH"), "data/kb/qdrant")

    STAGE: int = 5


settings = Settings()


def ensure_data_dirs() -> None:
    """Create runtime data directories if missing."""
    for path in (
        settings.UPLOADS_DIR,
        settings.DEBUG_DIR,
        settings.DATASET_IMAGES_DIR,
        settings.EXPLAINER_STATIC_DIR,
        settings.QDRANT_PATH,
        settings.KB_DIR,
        settings.KB_QDRANT_PATH,
    ):
        path.mkdir(parents=True, exist_ok=True)
