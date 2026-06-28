"""KB retrieval: hybrid dense + BM25 → MMR diversity → ranked chunks with citations."""

from __future__ import annotations

import asyncio
import logging
import re

import numpy as np

from backend.services.knowledge_base.embedder import get_embedder
from backend.services.knowledge_base.qdrant_client import collection_exists, get_qdrant_client
from backend.services.knowledge_base.sparse_index import search_sparse
from backend.shared.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_TOP_K = 8
_CANDIDATE_MULTIPLIER = 3
_MMR_LAMBDA = 0.7
_LABEL_QUERY_RE = re.compile(r"Technical documentation about ([^:]+)", re.IGNORECASE)
_DIAGRAM_TERMS = re.compile(
    r"\b(diagram|schematic|flowchart|figure|drawing|wiring|piping|layout|cross.?section)\b",
    re.IGNORECASE,
)


def _apply_label_keyword_boost(query: str, hit_text: str, base_score: float) -> float:
    match = _LABEL_QUERY_RE.search(query)
    if not match:
        return base_score
    label_terms = [word.lower() for word in match.group(1).split() if len(word) > 2]
    if not label_terms:
        return base_score
    text_lower = hit_text.lower()
    hits = sum(1 for term in label_terms if term in text_lower)
    if hits == 0:
        return base_score
    return min(1.0, base_score + 0.04 * hits)


def _apply_content_type_boost(
    query: str,
    content_type: str,
    base_score: float,
    *,
    prefer_content_type: str | None,
) -> float:
    preferred = prefer_content_type
    if preferred is None and _DIAGRAM_TERMS.search(query):
        preferred = "figure"
    if not preferred:
        return base_score
    if content_type == preferred:
        return min(1.0, base_score + settings.KB_CONTENT_TYPE_BOOST)
    if preferred == "figure" and content_type == "page_fallback":
        return min(1.0, base_score + settings.KB_CONTENT_TYPE_BOOST * 0.8)
    return base_score


def _apply_page_proximity_boost(
    page_num: int,
    base_score: float,
    *,
    page_hint: int | None,
) -> float:
    if not page_hint or page_num <= 0:
        return base_score
    distance = abs(page_num - page_hint)
    if distance == 0:
        return min(1.0, base_score + settings.KB_PAGE_PROXIMITY_BOOST)
    if distance <= 2:
        return min(1.0, base_score + settings.KB_PAGE_PROXIMITY_BOOST * 0.5)
    return base_score


def _collection_name(kb_id: str) -> str:
    return f"kb_{kb_id}"


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _mmr_select(
    query_vec: np.ndarray,
    candidates: list[dict],
    top_k: int,
    *,
    lambda_param: float = _MMR_LAMBDA,
) -> list[dict]:
    if len(candidates) <= top_k:
        return candidates

    selected: list[dict] = []
    remaining = list(candidates)
    query_vec = np.asarray(query_vec, dtype=np.float32)

    while remaining and len(selected) < top_k:
        best_idx = 0
        best_score = float("-inf")
        for idx, candidate in enumerate(remaining):
            vec = np.asarray(candidate["vector"], dtype=np.float32)
            relevance = _cosine_similarity(query_vec, vec)
            redundancy = 0.0
            if selected:
                redundancy = max(
                    _cosine_similarity(vec, np.asarray(s["vector"], dtype=np.float32))
                    for s in selected
                )
            mmr_score = lambda_param * relevance - (1 - lambda_param) * redundancy
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx
        selected.append(remaining.pop(best_idx))

    return selected


def _verify_collection_dimension(client, col: str, expected_dim: int) -> bool:
    try:
        info = client.get_collection(col)
        vectors = info.config.params.vectors
        actual_dim = vectors.size if hasattr(vectors, "size") else None
        if actual_dim is None:
            return True
        if actual_dim != expected_dim:
            logger.error(
                "Embedding dimension mismatch for %s: collection=%d embedder=%d. "
                "Re-ingest the KB with the current KB_EMBEDDING_MODEL.",
                col,
                actual_dim,
                expected_dim,
            )
            return False
    except Exception as exc:
        logger.warning("Could not verify collection dimension for %s: %s", col, exc)
    return True


def _fuse_hybrid_scores(
    dense_candidates: list[dict],
    sparse_hits: list[dict],
    *,
    dense_weight: float,
) -> list[dict]:
    """Reciprocal-rank-style fusion of dense and sparse candidate lists."""
    sparse_weight = 1.0 - dense_weight
    fused: dict[int, dict] = {}

    for rank, candidate in enumerate(dense_candidates):
        chunk_index = candidate.get("chunk_index")
        if chunk_index is None:
            continue
        dense_contrib = dense_weight / (rank + 1)
        fused[chunk_index] = {
            **candidate,
            "fusion_score": dense_contrib,
            "dense_score": candidate.get("score", 0.0),
            "sparse_score": 0.0,
        }

    for rank, hit in enumerate(sparse_hits):
        chunk_index = hit["chunk_index"]
        sparse_contrib = sparse_weight / (rank + 1)
        if chunk_index in fused:
            fused[chunk_index]["fusion_score"] += sparse_contrib
            fused[chunk_index]["sparse_score"] = hit.get("sparse_score", 0.0)
        else:
            fused[chunk_index] = {
                "text": hit["text"],
                "page_num": hit["page_num"],
                "source_name": "",
                "content_type": hit.get("content_type", "text"),
                "chunk_index": chunk_index,
                "vector": None,
                "score": 0.0,
                "fusion_score": sparse_contrib,
                "dense_score": 0.0,
                "sparse_score": hit.get("sparse_score", 0.0),
            }

    ordered = sorted(fused.values(), key=lambda c: c["fusion_score"], reverse=True)
    return ordered


def _sync_search(
    query: str,
    kb_id: str,
    qdrant_path: str,
    top_k: int,
    *,
    prefer_content_type: str | None = None,
    page_hint: int | None = None,
) -> list[dict]:
    col = _collection_name(kb_id)
    if not collection_exists(qdrant_path, col):
        logger.warning("KB collection %s not found", col)
        return []

    client = get_qdrant_client(qdrant_path)
    embedder = get_embedder()
    expected_dim = embedder.get_sentence_embedding_dimension()
    if not _verify_collection_dimension(client, col, expected_dim):
        return []

    query_vec = embedder.encode([query], show_progress_bar=False)[0]
    candidate_k = min(max(top_k * _CANDIDATE_MULTIPLIER, top_k), 24)

    response = client.query_points(
        col,
        query=query_vec.tolist(),
        limit=candidate_k,
        with_payload=True,
        with_vectors=True,
    )

    dense_candidates = []
    for hit in response.points:
        payload = hit.payload or {}
        vector = hit.vector
        if vector is None:
            continue
        chunk_index = payload.get("chunk_index", hit.id - 1)
        base_score = round(float(hit.score), 3)
        text = payload.get("text", "")
        content_type = payload.get("content_type", "text")
        page_num = payload.get("page_num", 0)
        score = _apply_label_keyword_boost(query, text, base_score)
        score = _apply_content_type_boost(
            query, content_type, score, prefer_content_type=prefer_content_type
        )
        score = _apply_page_proximity_boost(page_num, score, page_hint=page_hint)
        dense_candidates.append(
            {
                "text": text,
                "page_num": page_num,
                "source_name": payload.get("source_name", ""),
                "score": score,
                "content_type": content_type,
                "chunk_index": chunk_index,
                "vector": vector,
            }
        )

    sparse_hits = search_sparse(query, settings.KB_DIR, kb_id, top_k=candidate_k)
    fused = _fuse_hybrid_scores(
        dense_candidates,
        sparse_hits,
        dense_weight=settings.KB_HYBRID_DENSE_WEIGHT,
    )

    if not fused:
        return []

    for candidate in fused:
        if candidate.get("vector") is None and candidate.get("text"):
            candidate["vector"] = embedder.encode([candidate["text"]], show_progress_bar=False)[0]
        if not candidate.get("source_name"):
            for dense in dense_candidates:
                if dense["chunk_index"] == candidate.get("chunk_index"):
                    candidate["source_name"] = dense.get("source_name", "")
                    candidate["score"] = max(candidate.get("score", 0.0), dense["score"])
                    break

    with_vectors = [c for c in fused if c.get("vector") is not None]
    if not with_vectors:
        return [
            {
                "text": c["text"],
                "page_num": c["page_num"],
                "source_name": c.get("source_name", ""),
                "score": round(c.get("fusion_score", 0.0), 3),
                "content_type": c.get("content_type", "text"),
            }
            for c in fused[:top_k]
        ]

    selected = _mmr_select(query_vec, with_vectors, top_k)
    return [
        {
            "text": c["text"],
            "page_num": c["page_num"],
            "source_name": c["source_name"],
            "score": c["score"],
            "content_type": c["content_type"],
        }
        for c in selected
    ]


async def search_kb(
    query: str,
    kb_id: str,
    qdrant_path: str,
    top_k: int | None = None,
    *,
    prefer_content_type: str | None = None,
    page_hint: int | None = None,
) -> list[dict]:
    """Return top_k most relevant chunks from the KB, with citation metadata."""
    if not query.strip() or not kb_id:
        return []
    effective_top_k = top_k if top_k is not None else getattr(settings, "KB_TOP_K", _DEFAULT_TOP_K)
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(
            None,
            _sync_search,
            query,
            kb_id,
            qdrant_path,
            effective_top_k,
            prefer_content_type,
            page_hint,
        )
    except Exception as exc:
        logger.warning("KB search failed kb_id=%s query=%r: %s", kb_id, query, exc)
        return []
