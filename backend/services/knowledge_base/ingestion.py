"""PDF ingestion (Approach 3): Docling parse → 3 tracks (text / table-rows / figure-caption)
→ dense + BM25 sparse → hybrid Qdrant store keyed by page_id.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import tempfile
import uuid
from pathlib import Path

import httpx
from docling.document_converter import DocumentConverter
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    SparseVectorParams,
    VectorParams,
)

from backend.services.knowledge_base import sparse
from backend.services.knowledge_base.embedder import embed_texts, embedding_dimension
from backend.shared.config import settings

logger = logging.getLogger(__name__)

# Text chunking — sized to the BGE 512-token budget (~350 words leaves headroom).
_CHUNK_SIZE = 320
_CHUNK_OVERLAP = 60

# Stable, deterministic point IDs (same content → same id across re-ingest).
_ID_NAMESPACE = uuid.UUID("d711f3a2-0e6c-4c2a-9b6f-1f0e9a7c5b00")

_converter: DocumentConverter | None = None


def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        logger.info("Initialising Docling DocumentConverter (first use — downloads layout models ~500MB)")
        _converter = DocumentConverter()
        logger.info("Docling ready.")
    return _converter


# ---------------------------------------------------------------------------
# Figure description via local VLM (Qwen2.5-VL)
# ---------------------------------------------------------------------------

def _is_flowchart(caption: str) -> bool:
    keywords = ["procedure", "sequence", "flow", "steps", "process", "cycle", "diagram", "chart"]
    return any(kw in caption.lower() for kw in keywords)


def _describe_figure(image_bytes: bytes, caption: str) -> str:
    """Send a figure image to the local VLM and return a text description."""
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
# Docling parsing → flat element list (Step 2: every element carries page_id)
# ---------------------------------------------------------------------------

def _export_picture_bytes(picture_item, doc) -> bytes:
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


def _table_rows(table_item, doc) -> tuple[list[str], list[list[str]]]:
    """Return (header cells, list of body rows) for a Docling table, best-effort."""
    try:
        df = table_item.export_to_dataframe(doc)
        header = [str(c) for c in df.columns.tolist()]
        rows = [[("" if v is None else str(v)) for v in row] for row in df.values.tolist()]
        return header, rows
    except Exception as exc:
        logger.warning("Could not extract table rows: %s", exc)
        return [], []


def _dedupe_header(text: str) -> str:
    """Docling sometimes emits a heading's text doubled ('FOO FOO'); collapse it."""
    text = (text or "").strip()
    half = len(text) // 2
    if text and len(text) % 2 == 1 and text[:half].strip() == text[half + 1:].strip():
        return text[:half].strip()
    return text


def _parse_with_docling(pdf_path: Path) -> list[dict]:
    """Parse a PDF with Docling into a flat list of typed content elements."""
    converter = _get_converter()
    result = converter.convert(str(pdf_path))
    doc = result.document

    elements: list[dict] = []
    current_section = ""

    for item, _level in doc.iterate_items():
        item_type = type(item).__name__
        page_num = item.prov[0].page_no if item.prov else 0

        if item_type == "SectionHeaderItem":
            current_section = _dedupe_header(item.text)

        elif item_type == "TextItem":
            text = (item.text or "").strip()
            if text:
                elements.append({"zone": "text", "text": text,
                                 "section": current_section, "page_num": page_num})

        elif item_type == "ListItem":
            text = (item.text or "").strip()
            if text:
                elements.append({"zone": "text", "text": f"- {text}",
                                 "section": current_section, "page_num": page_num})

        elif item_type == "TableItem":
            header, rows = _table_rows(item, doc)
            try:
                table_md = item.export_to_markdown(doc)
            except Exception:
                table_md = ""
            elements.append({"zone": "table", "header": header, "rows": rows,
                             "markdown": table_md, "section": current_section,
                             "page_num": page_num})

        elif item_type == "PictureItem":
            caption_parts = []
            if hasattr(item, "captions") and item.captions:
                for cap in item.captions:
                    if hasattr(cap, "text") and cap.text:
                        caption_parts.append(cap.text)
            caption = " ".join(caption_parts).strip()
            elements.append({"zone": "figure",
                             "image_bytes": _export_picture_bytes(item, doc),
                             "caption": caption, "section": current_section,
                             "page_num": page_num})

    return elements


# ---------------------------------------------------------------------------
# Chunking (three tracks)
# ---------------------------------------------------------------------------

def _prefix(section: str, text: str) -> str:
    return f"[{section}] {text}" if section else text


def _chunk_text(section: str, page_num: int, text: str) -> list[dict]:
    """Track A — split prose/SOP text into overlapping word windows."""
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + _CHUNK_SIZE, len(words))
        chunks.append({"zone": "text", "page_num": page_num,
                       "text": _prefix(section, " ".join(words[start:end]))})
        if end == len(words):
            break
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
    return chunks


def _has_real_header(header: list[str]) -> bool:
    """Docling uses positional indices (0,1,2..) as columns when no header row exists."""
    return bool(header) and not all(h.strip().isdigit() for h in header)


def _is_contents_section(section: str) -> bool:
    s = (section or "").strip().lower()
    return s.startswith("content") or s.startswith("index") or s.startswith("table of content")


def _is_toc_table(section: str, rows: list[list[str]]) -> bool:
    """A table of contents / index: rows are '[section title, page number]' pairs.

    These pages list section names + their page numbers, so they hijack queries
    (e.g. 'fault diagnosis' matches the TOC row instead of the real content page).
    We skip them at ingestion so retrieval points at actual content.

    The section-header signal ('CONTENTS') is the reliable one. The structural
    signal requires exactly a [non-numeric title, numeric page(s)] two-cell shape,
    so genuine data tables (e.g. a programme chart with numeric columns) are kept.
    """
    if _is_contents_section(section):
        return True
    if not rows:
        return False
    toc_rows = 0
    for row in rows:
        cells = [str(v).strip() for v in row if str(v).strip()]
        if len(cells) != 2:
            continue
        title, last = cells
        title_has_letters = any(ch.isalpha() for ch in title)
        last_is_pages = all(tok.isdigit() and int(tok) <= 999 for tok in last.split())
        if title_has_letters and not title.replace(" ", "").isdigit() and last.split() and last_is_pages:
            toc_rows += 1
    return toc_rows >= max(2, len(rows) // 2)


def _chunk_table(elem: dict) -> list[dict]:
    """Track B — one self-describing chunk per row + one whole-table summary chunk."""
    section, page_num = elem["section"], elem["page_num"]
    header, rows = elem["header"], elem["rows"]
    chunks: list[dict] = []

    if _is_toc_table(section, rows):
        logger.info("Skipping table-of-contents table on page %d", page_num)
        return []

    if rows:
        real_header = _has_real_header(header)
        header_str = " | ".join(header) if real_header else ""
        for row in rows:
            if real_header:
                row_text = " | ".join(
                    f"{h}: {v}" for h, v in zip(header, row) if str(v).strip()
                )
                row_text = f"{header_str} || {row_text}" if row_text.strip() else ""
            else:
                row_text = " | ".join(str(v) for v in row if str(v).strip())
            if row_text.strip():
                chunks.append({"zone": "table_row", "page_num": page_num,
                               "text": _prefix(section, row_text)})

    summary = elem.get("markdown", "").strip()
    if summary:
        chunks.append({"zone": "table_summary", "page_num": page_num,
                       "text": _prefix(section, summary)})
    return chunks


def _chunk_figure(elem: dict) -> list[dict]:
    """Track C — VLM caption becomes one searchable chunk."""
    text = _describe_figure(elem["image_bytes"], elem["caption"])
    if not text.strip():
        return []
    return [{"zone": "caption", "page_num": elem["page_num"],
             "text": _prefix(elem["section"], text)}]


def _elements_to_chunks(elements: list[dict]) -> list[dict]:
    chunks: list[dict] = []
    for elem in elements:
        if elem["zone"] == "text":
            if _is_contents_section(elem["section"]):
                continue  # contents/index prose just lists section names — skip
            chunks.extend(_chunk_text(elem["section"], elem["page_num"], elem["text"]))
        elif elem["zone"] == "table":
            chunks.extend(_chunk_table(elem))
        elif elem["zone"] == "figure":
            chunks.extend(_chunk_figure(elem))
    return chunks


# ---------------------------------------------------------------------------
# Hybrid Qdrant store (Step 4)
# ---------------------------------------------------------------------------

def _collection_name(kb_id: str) -> str:
    return f"kb_{kb_id}"


def _point_id(document_id: str, page_num: int, zone: str, idx: int) -> str:
    return str(uuid.uuid5(_ID_NAMESPACE, f"{document_id}:{page_num}:{zone}:{idx}"))


def _sync_ingest(pdf_bytes: bytes, source_name: str, kb_id: str, qdrant_path: str) -> int:
    """Full ingestion pipeline — runs synchronously (call via executor)."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)
    try:
        elements = _parse_with_docling(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    logger.info("Docling extracted %d elements from %s", len(elements), source_name)

    chunks = _elements_to_chunks(elements)
    if not chunks:
        logger.warning("No content extracted from PDF: %s", source_name)
        return 0

    texts = [c["text"] for c in chunks]
    dense_vecs = embed_texts(texts)
    sparse_vecs = sparse.embed_documents(texts)

    client = QdrantClient(path=qdrant_path)
    col = _collection_name(kb_id)
    if col in [c.name for c in client.get_collections().collections]:
        client.delete_collection(col)
    client.create_collection(
        col,
        vectors_config={"dense": VectorParams(size=embedding_dimension(), distance=Distance.COSINE)},
        sparse_vectors_config={"sparse": SparseVectorParams()},
    )

    points = []
    for i, (chunk, dvec, svec) in enumerate(zip(chunks, dense_vecs, sparse_vecs)):
        page_num = chunk["page_num"]
        points.append(
            PointStruct(
                id=_point_id(kb_id, page_num, chunk["zone"], i),
                vector={"dense": dvec, "sparse": svec},
                payload={
                    "text": chunk["text"],
                    "document_id": kb_id,
                    "page_id": f"{kb_id}:p{page_num}",
                    "page_num": page_num,
                    "source_name": source_name,
                    "chunk_index": i,
                    "zone": chunk["zone"],
                    "content_type": chunk["zone"],  # back-compat with existing consumers
                },
            )
        )

    for batch_start in range(0, len(points), 100):
        client.upsert(col, points=points[batch_start: batch_start + 100])

    logger.info("Ingested %d chunks (%d elements) from %s into %s",
                len(points), len(elements), source_name, col)
    return len(points)


async def ingest_pdf(pdf_bytes: bytes, source_name: str, kb_id: str, qdrant_path: str) -> int:
    """Async wrapper — returns number of chunks ingested."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_ingest, pdf_bytes, source_name, kb_id, qdrant_path)


def delete_collection(kb_id: str, qdrant_path: str) -> None:
    client = QdrantClient(path=qdrant_path)
    col = _collection_name(kb_id)
    if col in [c.name for c in client.get_collections().collections]:
        client.delete_collection(col)
