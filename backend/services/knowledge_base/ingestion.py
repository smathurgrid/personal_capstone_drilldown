"""PDF ingestion: extract → chunk → embed → store in Qdrant."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from io import BytesIO

from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from backend.services.knowledge_base.embedder import get_embedder

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 400    # words per chunk
_CHUNK_OVERLAP = 80  # words overlap between consecutive chunks


def _extract_pages(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """Return list of (page_num_1indexed, text) for every page that has text."""
    reader = PdfReader(BytesIO(pdf_bytes))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append((i, text))
    return pages


def _chunk_text(page_num: int, text: str) -> list[dict]:
    """Split a page's text into overlapping word-window chunks."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + _CHUNK_SIZE, len(words))
        chunk_text = " ".join(words[start:end])
        chunks.append({"page_num": page_num, "text": chunk_text})
        if end == len(words):
            break
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
    return chunks


def _collection_name(kb_id: str) -> str:
    return f"kb_{kb_id}"


def _sync_ingest(pdf_bytes: bytes, source_name: str, kb_id: str, qdrant_path: str) -> int:
    """Full ingestion pipeline — runs synchronously (call via executor)."""
    embedder = get_embedder()
    client = QdrantClient(path=qdrant_path)
    col = _collection_name(kb_id)

    # Drop + recreate collection for idempotency
    existing = [c.name for c in client.get_collections().collections]
    if col in existing:
        client.delete_collection(col)

    dim = embedder.get_sentence_embedding_dimension()
    client.create_collection(col, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))

    pages = _extract_pages(pdf_bytes)
    all_chunks: list[dict] = []
    for page_num, text in pages:
        all_chunks.extend(_chunk_text(page_num, text))

    if not all_chunks:
        logger.warning("No text extracted from PDF: %s", source_name)
        return 0

    texts = [c["text"] for c in all_chunks]
    embeddings = embedder.encode(texts, show_progress_bar=False, batch_size=32)

    points = []
    for i, (chunk, vec) in enumerate(zip(all_chunks, embeddings)):
        uid = int(hashlib.md5(f"{kb_id}_{i}".encode()).hexdigest()[:8], 16)
        points.append(
            PointStruct(
                id=uid,
                vector=vec.tolist(),
                payload={
                    "text": chunk["text"],
                    "page_num": chunk["page_num"],
                    "source_name": source_name,
                    "chunk_index": i,
                },
            )
        )

    # Upload in batches of 100
    for batch_start in range(0, len(points), 100):
        client.upsert(col, points=points[batch_start : batch_start + 100])

    logger.info("Ingested %d chunks from %s into collection %s", len(points), source_name, col)
    return len(pages)


async def ingest_pdf(pdf_bytes: bytes, source_name: str, kb_id: str, qdrant_path: str) -> int:
    """Async wrapper — returns number of pages ingested."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _sync_ingest, pdf_bytes, source_name, kb_id, qdrant_path
    )


def delete_collection(kb_id: str, qdrant_path: str) -> None:
    client = QdrantClient(path=qdrant_path)
    col = _collection_name(kb_id)
    existing = [c.name for c in client.get_collections().collections]
    if col in existing:
        client.delete_collection(col)
