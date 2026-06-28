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
    # Where image generation runs: "ollama" (local), "mock", "remote" (Mac 2 Flux
    # worker), or "pool" (round-robin across several Ollama worker Macs).
    # Falls back to MODEL_PROVIDER so existing mock/ollama setups keep working unchanged.
    IMAGE_BACKEND: str = os.getenv("IMAGE_BACKEND", os.getenv("MODEL_PROVIDER", "ollama")).lower()
    # Mac 2 Flux worker base URL (distributed inference over Thunderbolt).
    REMOTE_FLUX_BASE: str = os.getenv("REMOTE_FLUX_BASE", "http://localhost:9000")

    # --- Multi-Mac image pool (powers the speculative prefetch fan-out) ---------
    # VLM (ranking + per-region analysis) stays on the MAIN Mac; image generation
    # is distributed across these worker endpoints. Both default to OLLAMA_BASE so
    # single-machine setups keep working with no extra config.
    VLM_OLLAMA_BASE: str = os.getenv("VLM_OLLAMA_BASE", OLLAMA_BASE)
    # The MAIN Mac's image endpoint — used to render the one-off PARENT/overview
    # image locally, keeping the worker Macs free for hotspot prefetch. Defaults
    # to the VLM box (same main Mac).
    MAIN_IMAGE_BASE: str = os.getenv("MAIN_IMAGE_BASE", VLM_OLLAMA_BASE)
    # Comma-separated Ollama endpoints serving the image model, one per worker Mac.
    IMAGE_OLLAMA_BASES: list[str] = [
        b.strip().rstrip("/")
        for b in os.getenv("IMAGE_OLLAMA_BASES", "").split(",")
        if b.strip()
    ] or [OLLAMA_BASE.rstrip("/")]
    # Concurrent image jobs per worker Mac (Flux is heavy; tune to each Mac's RAM).
    IMAGE_WORKER_CONCURRENCY: int = int(os.getenv("IMAGE_WORKER_CONCURRENCY", "1"))
    IMAGE_GEN_TIMEOUT: int = int(os.getenv("IMAGE_GEN_TIMEOUT", "300"))
    IMAGE_GEN_MAX_RETRIES: int = int(os.getenv("IMAGE_GEN_MAX_RETRIES", "2"))
    # Bind outgoing WORKER connections to this local LAN IP (this main Mac's en0
    # address) so they leave via the LAN, not a corporate VPN tunnel that would
    # black-hole the 192.168.x workers ("No route to host"). Empty = OS default.
    BIND_LAN_IP: str = os.getenv("BIND_LAN_IP", "")
    # Overlap the free-click CHILD generation (main Mac) with HOTSPOT generation
    # (workers): predict the child's hotspots from its prompt, render child +
    # hotspots in parallel, then locate the markers on the finished child.
    SPEC_OVERLAP: bool = os.getenv("SPEC_OVERLAP", "true").lower() in ("1", "true", "yes")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama").lower()
    LITELLM_PROXY_BASE: str = os.getenv("LITELLM_PROXY_BASE", "http://localhost:4000")
    LITELLM_API_KEY: str = os.getenv("LITELLM_API_KEY", "")
    AGENT_ORCHESTRATOR_MODEL: str = os.getenv("AGENT_ORCHESTRATOR_MODEL", "llama3.1")
    # Per-session JSONL trace of pi-agent tool calls + decision reasoning
    AGENT_LOG_DIR: Path = _path(os.getenv("AGENT_LOG_DIR"), "data/logs/agent")
    # SQLite store where completed speculative-drill sessions are persisted on end
    DRILL_SESSIONS_DB: Path = _path(
        os.getenv("DRILL_SESSIONS_DB"), "data/explainer/drill_sessions.db"
    )

    SAM2_PATH: str = os.getenv("SAM2_PATH", "")
    DEFAULT_GROUNDING_MODE: str = os.getenv("DEFAULT_GROUNDING_MODE", "")

    # Knowledge Base (RAG)
    KB_DIR: Path = _path(os.getenv("KB_DIR"), "data/kb")
    KB_QDRANT_PATH: Path = _path(os.getenv("KB_QDRANT_PATH"), "data/kb/qdrant")
    # Below this dense-cosine score a match is treated as too weak to cite (avoids
    # confidently showing a wrong page). Real drills query with the VLM's verbose
    # image description, which scores ~0.6-0.7 against the manual, so 0.6 lets genuine
    # drills cite while still suppressing near-empty matches. Tune via env if needed.
    KB_MIN_SCORE: float = float(os.getenv("KB_MIN_SCORE", "0.6"))

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
