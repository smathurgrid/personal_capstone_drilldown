"""Dense text embedder — pluggable model, loaded once and reused.

Default model is BAAI/bge-small-en-v1.5 (384-dim, 512-token context). It replaces
all-MiniLM-L6-v2, whose ~256-token cap silently truncated the back half of long chunks.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_embedder = None
_MODEL_NAME = os.getenv("KB_EMBED_MODEL", "BAAI/bge-small-en-v1.5")


def get_embedder():
    """Return the cached SentenceTransformer, loading it on first use."""
    global _embedder
    if _embedder is None:
        logger.info("Loading embedding model %s (first use — one-time download)", _MODEL_NAME)
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(_MODEL_NAME)
        logger.info("Embedding model loaded.")
    return _embedder


def embedding_dimension() -> int:
    """Vector size of the dense embedder (used to create the Qdrant collection)."""
    return get_embedder().get_sentence_embedding_dimension()


def embed_texts(texts: list[str], *, batch_size: int = 32) -> list[list[float]]:
    """Encode a list of texts into dense vectors (plain Python lists)."""
    if not texts:
        return []
    vecs = get_embedder().encode(texts, show_progress_bar=False, batch_size=batch_size)
    return [v.tolist() for v in vecs]
