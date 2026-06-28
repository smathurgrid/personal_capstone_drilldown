"""PDF ingestion: Docling parse → VLM/OCR figures → chunk → embed → store in Qdrant."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from qdrant_client.models import Distance, PointStruct, VectorParams

from backend.services.knowledge_base.embedder import get_embedder
from backend.services.knowledge_base.figure_enrichment import describe_figure
from backend.services.knowledge_base.pdf_fallback import build_page_fallback_elements, render_page_png
from backend.services.knowledge_base.qdrant_client import (
    get_qdrant_client,
    invalidate_collection_cache,
    register_collection,
    unregister_collection,
)
from backend.services.knowledge_base.sparse_index import build_sparse_index, delete_sparse_index
from backend.shared.config import settings

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 400
_CHUNK_OVERLAP = 80
_FIGURE_MAX_WORDS = 300

_converter: DocumentConverter | None = None


def _ensure_ocr_runtime() -> None:
    """Docling RapidOCR defaults to onnxruntime; torch backend lacks PP-OCRv6 models."""
    try:
        import onnxruntime  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "onnxruntime is required for KB PDF ingestion. "
            "Install it with: pip install onnxruntime"
        ) from exc


def _build_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions(
        ocr_options=RapidOcrOptions(
            backend="onnxruntime",
            lang=["english"],
        ),
    )
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)},
    )


def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        _ensure_ocr_runtime()
        logger.info(
            "Initialising Docling DocumentConverter (first use — downloads layout models ~500MB)"
        )
        _converter = _build_converter()
        logger.info("Docling ready (RapidOCR backend=onnxruntime).")
    return _converter


def _apply_section_prefix(text: str, section: str) -> str:
    if not section or not text.strip():
        return text
    tagged = f"[{section}]"
    if text.startswith(tagged):
        return text
    return f"{tagged} {text}"


def _is_low_signal_chunk(text: str, content_type: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    if content_type in ("figure", "page_fallback"):
        body = stripped.removeprefix("Figure:").strip()
        if len(body) < 12 and len(stripped.split()) < 4:
            return True
    return len(stripped.split()) < 3


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


def _parse_with_docling(pdf_path: Path) -> list[dict]:
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
            elements.append(
                {
                    "type": "figure",
                    "image_bytes": image_bytes,
                    "caption": caption,
                    "page_num": page_num,
                    "section": current_section,
                }
            )

    return elements


def _describe_figures_parallel(figures: list[dict]) -> list[str | None]:
    if not figures:
        return []
    concurrency = max(1, settings.KB_FIGURE_VLM_CONCURRENCY)
    results: list[str | None] = [None] * len(figures)

    def _run(fig: dict) -> str | None:
        if fig.get("skip_vlm") and fig.get("text"):
            return fig["text"]
        return describe_figure(
            fig.get("image_bytes") or b"",
            fig.get("caption") or "",
            section=fig.get("section") or "",
        )

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        future_map = {pool.submit(_run, fig): idx for idx, fig in enumerate(figures)}
        for future in as_completed(future_map):
            idx = future_map[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                logger.warning("Parallel figure description failed idx=%d: %s", idx, exc)
                caption = figures[idx].get("caption") or ""
                results[idx] = f"Figure: {caption}" if len(caption.split()) >= 3 else None

    return results


def _chunk_text(page_num: int, text: str, content_type: str = "text") -> list[dict]:
    words = text.split()
    if not words:
        return []

    max_single = _FIGURE_MAX_WORDS if content_type in ("figure", "page_fallback") else _CHUNK_SIZE * 2
    if content_type in ("table", "figure", "page_fallback") and len(words) <= max_single:
        return [{"page_num": page_num, "text": text, "content_type": content_type}]

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + _CHUNK_SIZE, len(words))
        chunks.append(
            {
                "page_num": page_num,
                "text": " ".join(words[start:end]),
                "content_type": content_type,
            }
        )
        if end == len(words):
            break
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
    return chunks


def _collection_name(kb_id: str) -> str:
    return f"kb_{kb_id}"


def _staging_collection_name(kb_id: str) -> str:
    return f"kb_{kb_id}_staging"


def _upsert_collection(
    client,
    col: str,
    points: list[PointStruct],
    expected_dim: int,
) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if col in existing:
        client.delete_collection(col)
        unregister_collection(str(settings.KB_QDRANT_PATH), col)
    invalidate_collection_cache(str(settings.KB_QDRANT_PATH))

    client.create_collection(
        col, vectors_config=VectorParams(size=expected_dim, distance=Distance.COSINE)
    )
    register_collection(str(settings.KB_QDRANT_PATH), col)
    for batch_start in range(0, len(points), 100):
        client.upsert(col, points=points[batch_start : batch_start + 100])


def _atomic_swap_collection(client, kb_id: str, points: list[PointStruct], expected_dim: int) -> None:
    """Write to staging first; swap into live collection only after staging succeeds."""
    col = _collection_name(kb_id)
    staging = _staging_collection_name(kb_id)
    qdrant_path = str(settings.KB_QDRANT_PATH)

    _upsert_collection(client, staging, points, expected_dim)

    existing = {c.name for c in client.get_collections().collections}
    if col in existing:
        client.delete_collection(col)
        unregister_collection(qdrant_path, col)
    invalidate_collection_cache(qdrant_path)

    client.create_collection(
        col, vectors_config=VectorParams(size=expected_dim, distance=Distance.COSINE)
    )
    register_collection(qdrant_path, col)
    for batch_start in range(0, len(points), 100):
        client.upsert(col, points=points[batch_start : batch_start + 100])

    if staging in {c.name for c in client.get_collections().collections}:
        client.delete_collection(staging)
        unregister_collection(qdrant_path, staging)
    invalidate_collection_cache(qdrant_path)


def _sync_ingest(pdf_bytes: bytes, source_name: str, kb_id: str, qdrant_path: str) -> dict:
    """Ingest PDF and return stats dict (chunk_count, page_count, figure_count, etc.)."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)

    stats = {
        "chunk_count": 0,
        "page_count": 0,
        "figure_count": 0,
        "page_fallback_count": 0,
        "failed_figure_exports": 0,
    }

    try:
        elements = _parse_with_docling(tmp_path)
        stats["failed_figure_exports"] = sum(
            1 for e in elements if e["type"] == "figure" and not e.get("image_bytes")
        )

        if settings.KB_PAGE_FALLBACK_ENABLED:
            for elem in elements:
                if elem["type"] != "figure" or elem.get("image_bytes"):
                    continue
                page_num = int(elem.get("page_num") or 0)
                if page_num <= 0:
                    continue
                try:
                    elem["image_bytes"] = render_page_png(
                        tmp_path, page_num, dpi=settings.KB_PAGE_FALLBACK_DPI
                    )
                    if elem["image_bytes"]:
                        stats["failed_figure_exports"] -= 1
                        logger.info("Recovered figure via page render page=%d", page_num)
                except Exception as exc:
                    logger.warning("Figure page render failed page=%d: %s", page_num, exc)

            fallbacks = build_page_fallback_elements(
                tmp_path,
                elements,
                dpi=settings.KB_PAGE_FALLBACK_DPI,
                source_name=source_name,
            )
            stats["page_fallback_count"] = len(fallbacks)
            elements.extend(fallbacks)
    finally:
        tmp_path.unlink(missing_ok=True)

    logger.info("Docling extracted %d elements from %s", len(elements), source_name)

    figures = [e for e in elements if e["type"] == "figure"]
    stats["figure_count"] = len(figures)
    figure_texts = _describe_figures_parallel(figures)
    figure_idx = 0

    all_chunks: list[dict] = []
    pending_header: dict | None = None
    page_nums: set[int] = set()

    for elem in elements:
        page_nums.add(int(elem.get("page_num") or 0))
        if elem["type"] == "figure":
            text = figure_texts[figure_idx]
            figure_idx += 1
            content_type = elem.get("content_type") or "figure"
            if not text or _is_low_signal_chunk(text, content_type):
                continue
            if pending_header:
                text = _apply_section_prefix(text, pending_header.get("text", "").strip())
            elif elem.get("section"):
                text = _apply_section_prefix(text, str(elem["section"]).strip())
            all_chunks.extend(_chunk_text(elem["page_num"], text, content_type=content_type))
        elif elem["type"] == "header":
            header_text = (elem.get("text") or "").strip()
            if header_text:
                pending_header = elem
        else:
            text = elem["text"]
            if pending_header:
                text = _apply_section_prefix(text, pending_header.get("text", "").strip())
            content_type = elem["type"]
            if _is_low_signal_chunk(text, content_type):
                continue
            all_chunks.extend(_chunk_text(elem["page_num"], text, content_type=content_type))

    stats["page_count"] = len({p for p in page_nums if p > 0})

    if not all_chunks:
        logger.warning("No content extracted from PDF: %s", source_name)
        delete_sparse_index(settings.KB_DIR, kb_id)
        return stats

    embedder = get_embedder()
    embedding_model = settings.KB_EMBEDDING_MODEL
    texts = [c["text"] for c in all_chunks]
    embeddings = embedder.encode(texts, show_progress_bar=False, batch_size=32)

    client = get_qdrant_client(qdrant_path)
    expected_dim = embedder.get_sentence_embedding_dimension()
    points = []
    for i, (chunk, vec) in enumerate(zip(all_chunks, embeddings)):
        points.append(
            PointStruct(
                id=i + 1,
                vector=vec.tolist(),
                payload={
                    "text": chunk["text"],
                    "page_num": chunk["page_num"],
                    "source_name": source_name,
                    "chunk_index": i,
                    "content_type": chunk["content_type"],
                    "embedding_model": embedding_model,
                },
            )
        )

    _atomic_swap_collection(client, kb_id, points, expected_dim)
    build_sparse_index(settings.KB_DIR, kb_id, all_chunks)

    stats["chunk_count"] = len(points)
    logger.info(
        "Ingested %d chunks (%d elements, %d figures, %d page fallbacks) from %s",
        len(points),
        len(elements),
        stats["figure_count"],
        stats["page_fallback_count"],
        source_name,
    )
    return stats


async def ingest_pdf(pdf_bytes: bytes, source_name: str, kb_id: str, qdrant_path: str) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _sync_ingest, pdf_bytes, source_name, kb_id, qdrant_path
    )


def delete_collection(kb_id: str, qdrant_path: str) -> None:
    client = get_qdrant_client(qdrant_path)
    col = _collection_name(kb_id)
    staging = _staging_collection_name(kb_id)
    existing = {c.name for c in client.get_collections().collections}
    for name in (col, staging):
        if name in existing:
            client.delete_collection(name)
            unregister_collection(qdrant_path, name)
    invalidate_collection_cache(qdrant_path)
    delete_sparse_index(settings.KB_DIR, kb_id)
