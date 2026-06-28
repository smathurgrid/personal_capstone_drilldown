"""Unified application settings loaded from environment / .env."""

from pathlib import Path
import os
import secrets

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
    API_PORT: int = int(os.getenv("API_PORT", "8001"))
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
        if origin.strip()
    ]
    CORS_ORIGIN_REGEX: str | None = os.getenv(
        "CORS_ORIGIN_REGEX",
        r"https?://(127\.0\.0\.1|localhost):\d+",
    )

    # Auth / persistence
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./data/drilldown.db",
    )
    AUTH_SECRET_KEY: str = os.getenv("AUTH_SECRET_KEY", "")
    AUTH_COOKIE_NAME: str = os.getenv("AUTH_COOKIE_NAME", "drilldown_session")
    AUTH_COOKIE_SECURE: bool = os.getenv("AUTH_COOKIE_SECURE", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    REDIS_CACHE_TTL_SECONDS: int = int(os.getenv("REDIS_CACHE_TTL_SECONDS", "86400"))

    # Ecommerce (Bhavya — Stage 2)
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    QDRANT_PATH: Path = _path(os.getenv("QDRANT_PATH"), "data/qdrant_storage")
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "fashion_products")
    UPLOADS_DIR: Path = _path(os.getenv("UPLOADS_DIR"), "data/ecommerce/uploads")
    PROFILE_UPLOADS_DIR: Path = _path(
        os.getenv("PROFILE_UPLOADS_DIR"), "data/profile/uploads"
    )
    DEBUG_DIR: Path = _path(os.getenv("DEBUG_DIR"), "data/ecommerce/debug")
    DATASET_IMAGES_DIR: Path = _path(
        os.getenv("DATASET_IMAGES_DIR"), "data/fashion-dataset/images"
    )

    # Explainer vision (Rohith — Stage 2)
    EXPLAINER_STATIC_DIR: Path = _path(
        os.getenv("EXPLAINER_STATIC_DIR"), "data/explainer/static"
    )
    HF_TOKEN: str = os.getenv("HF_TOKEN", "")
    _DEFAULT_VISION_MODEL: str = os.getenv(
        "EXPLAINER_VISION_MODEL",
        os.getenv("ROHITH_VISION_MODEL", "qwen3.5:9b"),
    )
    EXPLAINER_VISION_MODEL: str = _DEFAULT_VISION_MODEL

    # Explainer generation (Sid — Stage 2)
    OLLAMA_BASE: str = os.getenv("OLLAMA_BASE", "http://localhost:11434")
    IMAGE_MODEL: str = os.getenv("IMAGE_MODEL", "x/flux2-klein:4b")
    VISION_MODEL: str = os.getenv("VISION_MODEL", _DEFAULT_VISION_MODEL)
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
    KB_MIN_SCORE: float = float(os.getenv("KB_MIN_SCORE", "0.55"))
    KB_EMBEDDING_MODEL: str = os.getenv("KB_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    KB_FIGURE_VLM_CONCURRENCY: int = int(os.getenv("KB_FIGURE_VLM_CONCURRENCY", "2"))
    KB_TOP_K: int = int(os.getenv("KB_TOP_K", "8"))
    KB_HYBRID_DENSE_WEIGHT: float = float(os.getenv("KB_HYBRID_DENSE_WEIGHT", "0.65"))
    KB_CONTENT_TYPE_BOOST: float = float(os.getenv("KB_CONTENT_TYPE_BOOST", "0.06"))
    KB_PAGE_PROXIMITY_BOOST: float = float(os.getenv("KB_PAGE_PROXIMITY_BOOST", "0.05"))
    KB_PAGE_FALLBACK_ENABLED: bool = os.getenv("KB_PAGE_FALLBACK_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    KB_PAGE_FALLBACK_DPI: int = int(os.getenv("KB_PAGE_FALLBACK_DPI", "150"))

    STAGE: int = 5


settings = Settings()


if not settings.AUTH_SECRET_KEY:
    settings.AUTH_SECRET_KEY = secrets.token_urlsafe(48)


def ensure_data_dirs() -> None:
    """Create runtime data directories if missing."""
    for path in (
        settings.UPLOADS_DIR,
        settings.PROFILE_UPLOADS_DIR,
        settings.DEBUG_DIR,
        settings.DATASET_IMAGES_DIR,
        settings.EXPLAINER_STATIC_DIR,
        settings.EXPLAINER_STATIC_DIR.parent / "pending",
        settings.QDRANT_PATH,
        settings.KB_DIR,
        settings.KB_QDRANT_PATH,
    ):
        path.mkdir(parents=True, exist_ok=True)
