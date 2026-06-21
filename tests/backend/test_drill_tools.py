"""Tests for Layer 3 drill image prep and VLM response parsing."""

import io

from PIL import Image

from backend.services.explainer.drill_analyzer import _parse_vlm_sections
from backend.shared.image_utils import prepare_drill_surfaces


def test_prepare_drill_surfaces_pixel_crop():
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), color=(10, 20, 30)).save(buf, "PNG")
    global_b64, local_b64, w, h = prepare_drill_surfaces(buf.getvalue(), 200, 150, 60)
    assert w == 400 and h == 300
    assert global_b64 and local_b64


def test_parse_vlm_sections():
    raw = "ANALYSIS:\nClicked the engine block.\n\nIMAGE_PROMPT:\nCross-section of V8 engine."
    analysis, prompt = _parse_vlm_sections(raw)
    assert "engine block" in analysis
    assert "Cross-section" in prompt


def test_parse_vlm_sections_pov_mode_fallback():
    raw_empty = ""
    analysis, prompt = _parse_vlm_sections(raw_empty, drill_mode="pov")
    assert "first-person" in prompt
    assert "scenery" not in prompt or "first-person" in prompt

    raw_partial = "ANALYSIS:\na scenic window looking out at a harbor"
    analysis2, prompt2 = _parse_vlm_sections(raw_partial, drill_mode="pov")
    assert "harbor" in analysis2
    assert "first-person" in prompt2


def test_drill_analyzer_pov_prompt_building():
    from backend.shared.config import settings
    from backend.services.explainer.drill_analyzer import DrillAnalyzer
    analyzer = DrillAnalyzer(settings)
    prompt = analyzer._build_prompt(drill_mode="pov")
    assert "first-person" in prompt
    assert "OUTWARDS" in prompt
