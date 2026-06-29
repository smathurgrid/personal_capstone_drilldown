"""Figure OCR + structured VLM descriptions for KB ingestion."""

from __future__ import annotations

import base64
import io
import json
import logging
import re

from backend.shared.config import settings
from backend.shared.llm_client import get_llm_client

logger = logging.getLogger(__name__)

_FLOWCHART_KEYWORDS = (
    "procedure",
    "sequence",
    "flow",
    "steps",
    "process",
    "cycle",
    "diagram",
    "chart",
)

_STRUCTURED_PROMPT = """You are analyzing a technical figure from an industrial equipment manual.
Caption: '{caption}'
Section: '{section}'

Return a JSON object with these keys (use empty strings/lists if unknown):
{{
  "figure_type": "schematic|flowchart|photo|table_image|other",
  "components": ["labeled part names and part numbers"],
  "labels_and_text": ["all visible text, numbers, callouts"],
  "connections": ["arrows, flows, wiring, pipe paths"],
  "purpose": "one sentence on what this figure shows",
  "specs": ["torque, pressure, dimensions, model codes"],
  "steps": ["numbered steps if this is a procedure diagram"]
}}

Return ONLY valid JSON, no markdown fences."""

_GENERIC_PROMPT = """This is a technical diagram from an industrial equipment manual.
Caption: '{caption}'. Section: '{section}'.
Describe everything you see: components, labels, part numbers, arrows, flow paths,
connections, visible text, and the overall purpose. Be exhaustive and precise."""


def _vision_model() -> str:
    return settings.EXPLAINER_VISION_MODEL


def is_flowchart(caption: str) -> bool:
    lower = (caption or "").lower()
    return any(kw in lower for kw in _FLOWCHART_KEYWORDS)


def ocr_image_text(image_bytes: bytes) -> str:
    """Extract text from a figure via RapidOCR (bundled with Docling) when available."""
    if not image_bytes:
        return ""
    try:
        from PIL import Image
    except ImportError:
        return ""

    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
    except Exception:
        return ""

    engine = None
    for import_path in ("rapidocr_onnxruntime", "rapidocr"):
        try:
            module = __import__(import_path, fromlist=["RapidOCR"])
            engine = module.RapidOCR()
            break
        except ImportError:
            continue

    if engine is None:
        return ""

    try:
        result, _ = engine(img)
        if not result:
            return ""
        lines = [str(row[1]).strip() for row in result if len(row) > 1 and str(row[1]).strip()]
        return " ".join(lines)
    except Exception as exc:
        logger.debug("OCR failed: %s", exc)
        return ""


def _parse_structured_json(raw: str) -> dict | None:
    text = (raw or "").strip()
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _structured_to_prose(data: dict, *, caption: str) -> str:
    parts: list[str] = []
    if caption.strip():
        parts.append(f"Figure: {caption.strip()}")
    purpose = (data.get("purpose") or "").strip()
    if purpose:
        parts.append(f"Purpose: {purpose}")
    fig_type = (data.get("figure_type") or "").strip()
    if fig_type:
        parts.append(f"Type: {fig_type}")

    for key, label in (
        ("components", "Components"),
        ("labels_and_text", "Visible text"),
        ("connections", "Connections"),
        ("specs", "Specifications"),
        ("steps", "Procedure steps"),
    ):
        items = data.get(key) or []
        if isinstance(items, list) and items:
            cleaned = [str(i).strip() for i in items if str(i).strip()]
            if cleaned:
                parts.append(f"{label}: " + "; ".join(cleaned))
    return "\n".join(parts)


def describe_figure(
    image_bytes: bytes,
    caption: str,
    *,
    section: str = "",
) -> str | None:
    """Structured VLM description merged with OCR tokens for retrieval anchors."""
    if not image_bytes:
        return f"Figure: {caption}" if caption.strip() else None

    b64 = base64.b64encode(image_bytes).decode()
    llm = get_llm_client()
    section_text = section or "unknown section"
    caption_text = caption or "no caption"

    prompt = _STRUCTURED_PROMPT.format(caption=caption_text, section=section_text)
    description = ""
    try:
        raw = llm.chat_completion(
            _vision_model(),
            prompt,
            images=[b64],
            temperature=0.1,
            timeout=120,
            num_predict=700,
        ).strip()
        parsed = _parse_structured_json(raw)
        if parsed:
            description = _structured_to_prose(parsed, caption=caption_text)
        elif raw:
            description = raw
    except Exception as exc:
        logger.warning("Structured VLM figure description failed: %s", exc)

    if not description and is_flowchart(caption_text):
        flow_prompt = (
            f"Flowchart from manual. Caption: '{caption_text}'. "
            "Convert to numbered steps. For each decision: IF [condition] THEN [action] ELSE [other]."
        )
        try:
            description = llm.chat_completion(
                _vision_model(),
                flow_prompt,
                images=[b64],
                temperature=0.1,
                timeout=120,
                num_predict=600,
            ).strip()
        except Exception as exc:
            logger.warning("Flowchart VLM fallback failed: %s", exc)

    if not description:
        try:
            description = llm.chat_completion(
                _vision_model(),
                _GENERIC_PROMPT.format(caption=caption_text, section=section_text),
                images=[b64],
                temperature=0.1,
                timeout=120,
                num_predict=500,
            ).strip()
        except Exception as exc:
            logger.warning("Generic VLM figure description failed: %s", exc)

    ocr_text = ocr_image_text(image_bytes)
    if ocr_text:
        ocr_block = f"OCR text: {ocr_text}"
        description = f"{description}\n{ocr_block}" if description else ocr_block

    if not description:
        return f"Figure: {caption_text}" if caption_text.strip() else None
    if not description.startswith("Figure:") and caption_text.strip():
        description = f"Figure: {caption_text}\n{description}"
    return description
