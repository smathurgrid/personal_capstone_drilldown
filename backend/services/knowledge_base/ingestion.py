"""PDF ingestion: Docling parse → VLM for figures → chunk → embed → store in Qdrant."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import tempfile
from pathlib import Path

import httpx
from docling.document_converter import DocumentConverter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from backend.services.knowledge_base.embedder import get_embedder
from backend.shared.config import settings

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 400
_CHUNK_OVERLAP = 80

# Docling converter — instantiated once per process
_converter: DocumentConverter | None = None


def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        logger.info("Initialising Docling DocumentConverter (first use — downloads layout models ~500MB)")
        _converter = DocumentConverter()
        logger.info("Docling ready.")
    return _converter


# ---------------------------------------------------------------------------
# Figure description via local VLM
# ---------------------------------------------------------------------------

def _is_flowchart(caption: str) -> bool:
    keywords = ["procedure", "sequence", "flow", "steps", "process", "cycle", "diagram", "chart"]
    return any(kw in caption.lower() for kw in keywords)


def _describe_figure(image_bytes: bytes, caption: str) -> str:
    """Send a figure image to the local Qwen VLM and return a text description."""
    if not image_bytes:
        return caption

    b64 = base64.b64encode(image_bytes).decode()

    if _is_flowchart(caption):
        prompt = (
            f"This is a flowchart or process diagram from an industrial equipment manual. "
            f"Caption: '{caption}'. "
            "Convert this flowchart into numbered steps. "
            "For every decision diamond write: IF [condition] THEN [action] ELSE [other action]. "
            "List every step in order from start to end."
        )
    else:
        prompt = (
            f"This is a technical diagram from an industrial equipment manual. "
            f"Caption: '{caption}'. "
            "Describe everything you see in detail: all components, labels, part numbers, "
            "arrows and their directions, flow paths, connections between parts, any visible "
            "text or numbers, and the overall purpose of this diagram."
        )

    try:
        resp = httpx.post(
            f"{settings.OLLAMA_BASE}/api/generate",
            json={
                "model": settings.VISION_MODEL,
                "prompt": prompt,
                "images": [b64],
                "stream": False,
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        description = resp.json().get("response", "").strip()
        return f"Figure: {caption}\n{description}" if description else f"Figure: {caption}"
    except Exception as exc:
        logger.warning("VLM figure description failed: %s", exc)
        return f"Figure: {caption}"


# ---------------------------------------------------------------------------
# Docling parsing
# ---------------------------------------------------------------------------

def _export_picture_bytes(picture_item, doc) -> bytes:
    """Export a PictureItem to PNG bytes. Returns empty bytes on failure."""
    from io import BytesIO
    try:
        pil_image = picture_item.get_image(doc)
        if pil_image is None:
            return b""
        buf = BytesIO()
        pil_image.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as exc:
        logger.warning("Could not export picture: %s", exc)
        return b""


def _parse_with_docling(pdf_path: Path) -> list[dict]:
    """Parse a PDF with Docling and return a flat list of content elements."""
    converter = _get_converter()
    result = converter.convert(str(pdf_path))
    doc = result.document

    elements = []
    current_section = ""

    for item, _level in doc.iterate_items():
        item_type = type(item).__name__
        page_num = item.prov[0].page_no if item.prov else 0

        if item_type == "SectionHeaderItem":
            current_section = item.text or ""
            elements.append({"type": "header", "text": current_section, "page_num": page_num})

        elif item_type == "TextItem":
            text = item.text or ""
            if text.strip():
                prefixed = f"[{current_section}] {text}" if current_section else text
                elements.append({"type": "text", "text": prefixed, "page_num": page_num})

        elif item_type == "ListItem":
            text = item.text or ""
            if text.strip():
                prefixed = f"[{current_section}] {text}" if current_section else text
                elements.append({"type": "text", "text": f"- {prefixed}", "page_num": page_num})

        elif item_type == "TableItem":
            try:
                table_md = item.export_to_markdown(doc)
            except Exception:
                table_md = ""
            if table_md.strip():
                prefixed = f"[{current_section}]\n{table_md}" if current_section else table_md
                elements.append({"type": "table", "text": prefixed, "page_num": page_num})

        elif item_type == "PictureItem":
            caption_parts = []
            if hasattr(item, "captions") and item.captions:
                for cap in item.captions:
                    if hasattr(cap, "text") and cap.text:
                        caption_parts.append(cap.text)
            caption = " ".join(caption_parts).strip()
            image_bytes = _export_picture_bytes(item, doc)
            elements.append({
                "type": "figure",
                "image_bytes": image_bytes,
                "caption": caption,
                "page_num": page_num,
            })

    return elements


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _chunk_text(page_num: int, text: str, content_type: str = "text") -> list[dict]:
    """Split text into overlapping word-window chunks."""
    words = text.split()
    if not words:
        return []

    # Tables and figures: keep as single chunk unless very long
    if content_type in ("table", "figure") and len(words) <= _CHUNK_SIZE * 2:
        return [{"page_num": page_num, "text": text, "content_type": content_type}]

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + _CHUNK_SIZE, len(words))
        chunks.append({
            "page_num": page_num,
            "text": " ".join(words[start:end]),
            "content_type": content_type,
        })
        if end == len(words):
            break
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
    return chunks


# ---------------------------------------------------------------------------
# Main ingestion pipeline
# ---------------------------------------------------------------------------

def _collection_name(kb_id: str) -> str:
    return f"kb_{kb_id}"


def _sync_ingest(pdf_bytes: bytes, source_name: str, kb_id: str, qdrant_path: str) -> int:
    """Full ingestion pipeline — runs synchronously (call via executor)."""
    # Write bytes to a temp file — Docling needs a file path
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)

    try:
        elements = _parse_with_docling(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    logger.info("Docling extracted %d elements from %s", len(elements), source_name)

    all_chunks: list[dict] = []
    for elem in elements:
        if elem["type"] == "figure":
            text = _describe_figure(elem["image_bytes"], elem["caption"])
            all_chunks.extend(_chunk_text(elem["page_num"], text, content_type="figure"))
        elif elem["type"] == "header":
            # Headers are prepended to following chunks as context — don't store alone
            pass
        else:
            all_chunks.extend(_chunk_text(elem["page_num"], elem["text"],
                                          content_type=elem["type"]))

    if not all_chunks:
        logger.warning("No content extracted from PDF: %s", source_name)
        return 0

    embedder = get_embedder()
    client = QdrantClient(path=qdrant_path)
    col = _collection_name(kb_id)

    # Drop + recreate collection for idempotency
    existing = [c.name for c in client.get_collections().collections]
    if col in existing:
        client.delete_collection(col)

    dim = embedder.get_embedding_dimension()
    client.create_collection(col, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))

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
                    "content_type": chunk["content_type"],
                },
            )
        )

    for batch_start in range(0, len(points), 100):
        client.upsert(col, points=points[batch_start: batch_start + 100])

    logger.info(
        "Ingested %d chunks (%d elements) from %s into collection %s",
        len(points), len(elements), source_name, col,
    )
    return len(points)


async def ingest_pdf(pdf_bytes: bytes, source_name: str, kb_id: str, qdrant_path: str) -> int:
    """Async wrapper — returns number of chunks ingested."""
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
