"""Singleton sentence-transformers embedder — loaded once, reused everywhere."""

from __future__ import annotations

import logging

from backend.shared.config import settings

logger = logging.getLogger(__name__)

_embedder = None
_loaded_model_name: str | None = None


def get_embedder():
    global _embedder, _loaded_model_name
    model_name = settings.KB_EMBEDDING_MODEL
    if _embedder is None or _loaded_model_name != model_name:
        logger.info(
            "Loading embedding model %s (first use — one-time download)",
            model_name,
        )
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(model_name)
        _loaded_model_name = model_name
        logger.info("Embedding model loaded.")
    return _embedder
