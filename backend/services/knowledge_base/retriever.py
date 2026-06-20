"""KB retrieval: embed query → Qdrant search → ranked chunks with citations."""

from __future__ import annotations

import asyncio
import logging

from qdrant_client import QdrantClient

from backend.services.knowledge_base.embedder import get_embedder

logger = logging.getLogger(__name__)


def _collection_name(kb_id: str) -> str:
    return f"kb_{kb_id}"


def _sync_search(query: str, kb_id: str, qdrant_path: str, top_k: int) -> list[dict]:
    client = QdrantClient(path=qdrant_path)
    col = _collection_name(kb_id)

    existing = [c.name for c in client.get_collections().collections]
    if col not in existing:
        logger.warning("KB collection %s not found", col)
        return []

    embedder = get_embedder()
    query_vec = embedder.encode([query], show_progress_bar=False)[0].tolist()

    response = client.query_points(col, query=query_vec, limit=top_k, with_payload=True)
    hits = response.points

    results = []
    for hit in hits:
        payload = hit.payload or {}
        results.append(
            {
                "text": payload.get("text", ""),
                "page_num": payload.get("page_num", 0),
                "source_name": payload.get("source_name", ""),
                "score": round(float(hit.score), 3),
                "content_type": payload.get("content_type", "text"),
            }
        )
    return results


async def search_kb(query: str, kb_id: str, qdrant_path: str, top_k: int = 4) -> list[dict]:
    """Return top_k most relevant chunks from the KB, with citation metadata."""
    if not query.strip() or not kb_id:
        return []
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _sync_search, query, kb_id, qdrant_path, top_k)
    except Exception as exc:
        logger.warning("KB search failed kb_id=%s query=%r: %s", kb_id, query, exc)
        return []
