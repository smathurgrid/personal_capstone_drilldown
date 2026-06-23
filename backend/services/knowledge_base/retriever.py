"""KB retrieval (Approach 3): hybrid dense + BM25 search with RRF fusion,
then re-join all chunks on the matched page(s) into one context block.
"""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict

from qdrant_client import QdrantClient
from qdrant_client.models import Fusion, FusionQuery, Prefetch

from backend.services.knowledge_base import sparse
from backend.services.knowledge_base.embedder import embed_texts

logger = logging.getLogger(__name__)

# How many page neighbours to pull back when re-joining a winning page.
_PER_PAGE_LIMIT = 12
# Preferred ordering of zones within a re-joined page block.
_ZONE_ORDER = {"text": 0, "table_summary": 1, "table_row": 2, "caption": 3}


def _collection_name(kb_id: str) -> str:
    return f"kb_{kb_id}"


def _hit_to_dict(hit) -> dict:
    payload = hit.payload or {}
    return {
        "text": payload.get("text", ""),
        "page_id": payload.get("page_id", ""),
        "page_num": payload.get("page_num", 0),
        "source_name": payload.get("source_name", ""),
        "zone": payload.get("zone", payload.get("content_type", "text")),
        "content_type": payload.get("content_type", "text"),
        "score": round(float(hit.score), 3),
    }


def _hybrid_query(client, col: str, query: str, top_k: int) -> list[dict]:
    """Run a single fused dense+BM25 query against an already-open client."""
    dense_vec = embed_texts([query])[0]
    sparse_vec = sparse.embed_query(query)
    response = client.query_points(
        col,
        prefetch=[
            Prefetch(query=dense_vec, using="dense", limit=max(top_k * 4, 20)),
            Prefetch(query=sparse_vec, using="sparse", limit=max(top_k * 4, 20)),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )
    return [_hit_to_dict(h) for h in response.points]


def _sync_search(query: str, kb_id: str, qdrant_path: str, top_k: int) -> list[dict]:
    client = QdrantClient(path=qdrant_path)
    col = _collection_name(kb_id)
    if col not in [c.name for c in client.get_collections().collections]:
        logger.warning("KB collection %s not found", col)
        return []
    return _hybrid_query(client, col, query, top_k)


def _sync_search_page(query: str, kb_id: str, qdrant_path: str, top_pages: int) -> list[dict]:
    """Hybrid search, then re-join every chunk on each winning page into one block.

    Opens a single Qdrant client (file-mode allows only one per path per process).
    """
    client = QdrantClient(path=qdrant_path)
    col = _collection_name(kb_id)
    if col not in [c.name for c in client.get_collections().collections]:
        logger.warning("KB collection %s not found", col)
        return []

    hits = _hybrid_query(client, col, query, top_k=max(top_pages * 3, 8))
    if not hits:
        return []

    # Winning pages, in fused-rank order, deduped.
    page_order: "OrderedDict[str, dict]" = OrderedDict()
    for h in hits:
        if h["page_id"] and h["page_id"] not in page_order:
            page_order[h["page_id"]] = h
        if len(page_order) >= top_pages:
            break

    from qdrant_client.models import FieldCondition, Filter, MatchValue

    dense_vec = embed_texts([query])[0]
    blocks: list[dict] = []
    for page_id, best in page_order.items():
        page_hits = client.query_points(
            col,
            query=dense_vec,
            using="dense",
            query_filter=Filter(must=[FieldCondition(key="page_id", match=MatchValue(value=page_id))]),
            limit=_PER_PAGE_LIMIT,
            with_payload=True,
        ).points
        page_rows = [_hit_to_dict(h) for h in page_hits]
        # Confidence = best dense cosine similarity on the page (a real 0-1 relevance
        # measure), not the RRF rank score which is high even for poor matches.
        page_score = round(max((r["score"] for r in page_rows), default=0.0), 3)
        rows = sorted(page_rows, key=lambda r: _ZONE_ORDER.get(r["zone"], 9))
        block_text = "\n\n".join(r["text"] for r in rows if r["text"].strip())
        blocks.append({
            "page_id": page_id,
            "page_num": best["page_num"],
            "source_name": best["source_name"],
            "score": page_score,
            "text": block_text,
            "citation": f"{best['source_name']}, page {best['page_num']}",
            "chunks": rows,
        })
    blocks.sort(key=lambda b: b["score"], reverse=True)
    return blocks


async def search_kb(query: str, kb_id: str, qdrant_path: str, top_k: int = 4) -> list[dict]:
    """Top_k most relevant chunks (hybrid dense+BM25), with citation metadata."""
    if not query.strip() or not kb_id:
        return []
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _sync_search, query, kb_id, qdrant_path, top_k)
    except Exception as exc:
        logger.warning("KB search failed kb_id=%s query=%r: %s", kb_id, query, exc)
        return []


async def search_kb_pages(query: str, kb_id: str, qdrant_path: str, top_pages: int = 2) -> list[dict]:
    """Hybrid search re-joined per page — each result is a full-page context block."""
    if not query.strip() or not kb_id:
        return []
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _sync_search_page, query, kb_id, qdrant_path, top_pages)
    except Exception as exc:
        logger.warning("KB page search failed kb_id=%s query=%r: %s", kb_id, query, exc)
        return []
