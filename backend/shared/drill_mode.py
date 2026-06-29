"""Drill mode normalization and shared text helpers."""

from __future__ import annotations

import re

_DRILL_MODE_ALIASES = {
    "pov": "pov",
    "perspective": "pov",
    "outward": "pov",
    "first-person": "pov",
    "inside": "inside",
    "macro": "inside",
    "zoom": "inside",
    "cross-section": "inside",
}


def normalize_drill_mode(value: str | None, *, default: str = "inside") -> str:
    """Normalize drill mode strings; raise ValueError on unknown values."""
    if value is None or not str(value).strip():
        return default
    key = str(value).strip().lower()
    if key in _DRILL_MODE_ALIASES:
        return _DRILL_MODE_ALIASES[key]
    raise ValueError(f"drillMode must be 'inside' or 'pov', got {value!r}")


def extract_analysis_snippet(analysis: str, *, max_len: int = 120) -> str:
    """Extract a retrieval-safe snippet without breaking on Fig. 3.2 or 3.5 mm."""
    text = (analysis or "").strip()
    if not text:
        return ""

    # Sentence boundary: period not sandwiched between digits, followed by space + letter
    parts = re.split(r"(?<!\d)\.(?!\d)\s+(?=[A-Z\"'])", text, maxsplit=1)
    snippet = parts[0].strip().rstrip(".")

    if len(snippet) < 8 and len(text) > len(snippet):
        snippet = text[:max_len].rsplit(" ", 1)[0] if len(text) > max_len else text

    return snippet[:max_len].strip()


def build_kb_retrieval_snippet(analysis: str, *, max_len: int = 280) -> str:
    """Multi-sentence snippet for KB retrieval — keeps part numbers in later sentences."""
    text = (analysis or "").strip()
    if not text:
        return ""

    sentences = re.split(r"(?<!\d)\.(?!\d)\s+(?=[A-Z\"'])", text)
    parts: list[str] = []
    length = 0
    for sentence in sentences:
        sentence = sentence.strip().rstrip(".")
        if not sentence:
            continue
        projected = length + len(sentence) + (2 if parts else 0)
        if projected > max_len and parts:
            break
        parts.append(sentence)
        length = projected
        if len(parts) >= 3:
            break

    if not parts:
        return extract_analysis_snippet(text, max_len=max_len)

    joined = ". ".join(parts)
    if len(joined) > max_len:
        return joined[:max_len].rsplit(" ", 1)[0].strip()
    return joined


def build_flux_prompt(drill_topic: str, drill_mode: str, *, style_desc: str = "") -> str:
    """Wrap VLM image prompt with mode-specific instructions for text-to-image (Flux)."""
    topic = (drill_topic or "").strip()
    if not topic:
        topic = "the selected region"

    if drill_mode == "pov":
        parts = [
            "First-person photorealistic wide-angle photograph looking outward from the selected point.",
            "Natural eye-level perspective showing the surrounding environment and atmosphere.",
            "No text, labels, watermarks, red circles, or UI markers.",
            topic,
        ]
        if style_desc.strip():
            parts.insert(-1, f"Match lighting and color palette: {style_desc.strip()}")
        return " ".join(parts)

    style_snippet = ""
    if style_desc.strip():
        style_snippet = f"Match the exact visual style, colors, medium, and aesthetic of the previous context: {style_desc.strip()}. "

    return (
        "Professional scientific cross-section illustration, technical cutaway diagram, "
        "revealing the inner structural layers and microscopic details inside. "
        f"{style_snippet}"
        "High-resolution 3D medical or industrial blueprint render, clean lighting, no text or labels. "
        f"{topic}"
    )
