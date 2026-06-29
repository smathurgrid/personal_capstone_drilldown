"""Page-level PDF rasterization fallback when Docling misses visual content."""

from __future__ import annotations

import base64
import logging
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


def _page_text_density(elements: list[dict]) -> dict[int, dict[str, int]]:
    stats: dict[int, dict[str, int]] = defaultdict(lambda: {"text_chars": 0, "figures": 0})
    for elem in elements:
        page = int(elem.get("page_num") or 0)
        if page <= 0:
            continue
        if elem["type"] == "figure":
            stats[page]["figures"] += 1
            if not elem.get("image_bytes"):
                stats[page]["failed_figures"] = stats[page].get("failed_figures", 0) + 1
        elif elem["type"] in ("text", "table", "header"):
            stats[page]["text_chars"] += len((elem.get("text") or ""))
    return stats


def pages_needing_fallback(
    elements: list[dict],
    *,
    min_text_chars: int = 80,
) -> set[int]:
    """Pages that are image-heavy or had failed figure exports."""
    stats = _page_text_density(elements)
    needed: set[int] = set()
    for page, s in stats.items():
        if s.get("failed_figures", 0) > 0:
            needed.add(page)
        if s["text_chars"] < min_text_chars and s["figures"] == 0:
            needed.add(page)
    return needed


def render_page_png(pdf_path: Path, page_num: int, *, dpi: int = 150) -> bytes:
    """Rasterize a single PDF page to PNG bytes via PyMuPDF."""
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError("PyMuPDF (pymupdf) is required for page fallback rendering") from exc

    doc = fitz.open(str(pdf_path))
    try:
        if page_num < 1 or page_num > len(doc):
            return b""
        page = doc[page_num - 1]
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


def describe_page_fallback(
    image_bytes: bytes,
    page_num: int,
    *,
    source_name: str,
) -> str | None:
    """VLM description for a full page when structured extraction is sparse."""
    if not image_bytes:
        return None

    from backend.services.knowledge_base.figure_enrichment import describe_figure

    caption = f"Page {page_num} visual content from {source_name}"
    return describe_figure(
        image_bytes,
        caption,
        section=f"Page {page_num}",
    )


def build_page_fallback_elements(
    pdf_path: Path,
    elements: list[dict],
    *,
    dpi: int = 150,
    source_name: str = "",
) -> list[dict]:
    """Add synthetic figure elements for pages Docling under-extracted."""
    pages = pages_needing_fallback(elements)
    if not pages:
        return []

    fallback_elements: list[dict] = []
    for page_num in sorted(pages):
        try:
            png_bytes = render_page_png(pdf_path, page_num, dpi=dpi)
        except Exception as exc:
            logger.warning("Page render failed page=%d: %s", page_num, exc)
            continue
        if not png_bytes:
            continue
        description = describe_page_fallback(png_bytes, page_num, source_name=source_name)
        if not description:
            continue
        fallback_elements.append(
            {
                "type": "figure",
                "image_bytes": png_bytes,
                "caption": f"Page {page_num} (rendered fallback)",
                "page_num": page_num,
                "text": description,
                "content_type": "page_fallback",
                "skip_vlm": True,
            }
        )
        logger.info("Added page fallback for page %d (%d bytes)", page_num, len(png_bytes))
    return fallback_elements
