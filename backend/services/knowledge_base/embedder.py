"""Singleton sentence-transformers embedder — loaded once, reused everywhere."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_embedder = None
_MODEL_NAME = "all-MiniLM-L6-v2"


def get_embedder():
    global _embedder
    if _embedder is None:
        logger.info("Loading embedding model %s (first use — one-time download ~80MB)", _MODEL_NAME)
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(_MODEL_NAME)
        logger.info("Embedding model loaded.")
    return _embedder
