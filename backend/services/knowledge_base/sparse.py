"""BM25 sparse embeddings via fastembed — local, no external service.

Sparse vectors capture exact-keyword matches (part numbers, fault codes, programme
names) that dense/meaning vectors miss. Stored alongside the dense vector in Qdrant
as a named "sparse" vector, then fused with dense results at query time (RRF).
"""

from __future__ import annotations

import logging

from qdrant_client.models import SparseVector

logger = logging.getLogger(__name__)

_model = None
_MODEL_NAME = "Qdrant/bm25"


def _get_model():
    global _model
    if _model is None:
        logger.info("Loading BM25 sparse model %s (first use)", _MODEL_NAME)
        from fastembed import SparseTextEmbedding
        _model = SparseTextEmbedding(model_name=_MODEL_NAME)
        logger.info("BM25 sparse model loaded.")
    return _model


def _to_sparse_vector(emb) -> SparseVector:
    return SparseVector(indices=emb.indices.tolist(), values=emb.values.tolist())


def embed_documents(texts: list[str]) -> list[SparseVector]:
    """Sparse vectors for stored chunks (corpus-side encoding)."""
    if not texts:
        return []
    return [_to_sparse_vector(e) for e in _get_model().embed(texts)]


def embed_query(text: str) -> SparseVector:
    """Sparse vector for a search query (query-side encoding)."""
    embs = list(_get_model().query_embed(text))
    return _to_sparse_vector(embs[0])
