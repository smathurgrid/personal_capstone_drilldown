"""Per-click dual-image VLM analysis (F3 + F4)."""

from __future__ import annotations

import asyncio
import base64
import io
import re
import logging
from typing import Literal

from PIL import Image

from backend.shared.config import Settings
from backend.shared.drill_mode import extract_analysis_snippet
from backend.shared.llm_client import LLMClient

logger = logging.getLogger(__name__)

PovContextKind = Literal["segment", "wide", "none"]

_TWO_TASK_PROMPT = """You are an expert technical illustrator analyzing a drill-down selection.

You receive TWO images:
1. Image 1 — Full scene with a red circle marking WHERE the user clicked (global context).
2. Image 2 — Cropped close-up of the region under the click (local detail).

TASK 1 — ANALYSIS: Describe what was clicked and its role in the larger scene.
TASK 2 — IMAGE PROMPT: Write a precise, detailed prompt for an image generation model to illustrate what is PHYSICALLY INSIDE or BENEATH that specific target component (an internal cross-section, microscopic slice, or material cutaway diagram).
IMPORTANT: Focus strictly on the isolated target component itself (e.g., if you click a clock hand, focus only on the hand's internal metal, gears, or molecular structure; ignore the wider dial background completely). The prompt MUST preserve the exact visual medium (photograph vs illustration vs 3D render), color palette, textures, and lighting of the previous context. No text, labels, or UI markers.

Respond in exactly this format:
ANALYSIS:
<your analysis text>

IMAGE_PROMPT:
<your generation prompt>"""

_TWO_TASK_POV_PROMPT_SEGMENT = """You are an expert cinematic photographer analyzing a drill-down selection.

You receive TWO images:
1. Image 1 — Full scene with a red circle marking WHERE the user clicked.
2. Image 2 — A crop of the exact selected object/region boundary (what the user clicked on).

TASK 1 — ANALYSIS: Describe what was clicked, its location in the scene, and what the surrounding environment would look like when viewed outward from that point.
TASK 2 — IMAGE PROMPT: Write a detailed prompt for an image generation model to create a first-person point-of-view (POV) photograph looking OUTWARDS from exactly this location toward the surrounding room, environment, or scenery. Include camera perspective, lighting, color palette, and atmosphere matching Image 1. No text, labels, or annotations in the generated image.

Respond in exactly this format:
ANALYSIS:
<your analysis text>

IMAGE_PROMPT:
<your generation prompt>"""

_TWO_TASK_POV_PROMPT_WIDE = """You are an expert cinematic photographer analyzing a drill-down selection.

You receive TWO images:
1. Image 1 — Full scene with a red circle marking WHERE the user clicked.
2. Image 2 — A wide surrounding context crop showing the environment near the click.

TASK 1 — ANALYSIS: Describe what was clicked, its location in the scene, and what the surrounding environment would look like when viewed outward from that point.
TASK 2 — IMAGE PROMPT: Write a detailed prompt for an image generation model to create a first-person point-of-view (POV) photograph looking OUTWARDS from exactly this location toward the surrounding room, environment, or scenery. Include camera perspective, lighting, color palette, and atmosphere matching Image 1. No text, labels, or annotations in the generated image.

Respond in exactly this format:
ANALYSIS:
<your analysis text>

IMAGE_PROMPT:
<your generation prompt>"""

_TWO_TASK_POV_PROMPT_GLOBAL_ONLY = """You are an expert cinematic photographer analyzing a drill-down selection.

You receive ONE image — the full scene with a red circle marking WHERE the user clicked.

TASK 1 — ANALYSIS: Describe what was clicked, its location in the scene, and what the surrounding environment would look like when viewed outward from that point.
TASK 2 — IMAGE PROMPT: Write a detailed prompt for an image generation model to create a first-person point-of-view (POV) photograph looking OUTWARDS from exactly this location toward the surrounding room, environment, or scenery. Include camera perspective, lighting, color palette, and atmosphere matching Image 1. No text, labels, or annotations in the generated image.

Respond in exactly this format:
ANALYSIS:
<your analysis text>

IMAGE_PROMPT:
<your generation prompt>"""

_LABEL_HINT_PREFIX = (
    "The user selected the label '{label}' at the marked click location. "
    "Confirm or correct the object name in your ANALYSIS, then produce IMAGE_PROMPT.\n\n"
)


def _parse_vlm_sections(raw: str, drill_mode: str = "inside") -> tuple[str, str]:
    analysis = ""
    image_prompt = ""
    analysis_match = re.search(
        r"ANALYSIS:\s*(.*?)(?=IMAGE_PROMPT:|$)", raw, re.DOTALL | re.IGNORECASE
    )
    prompt_match = re.search(r"IMAGE_PROMPT:\s*(.*)$", raw, re.DOTALL | re.IGNORECASE)
    if analysis_match:
        analysis = analysis_match.group(1).strip()
    if prompt_match:
        image_prompt = prompt_match.group(1).strip()
    snippet = extract_analysis_snippet(analysis) if analysis else ""
    if not analysis and not image_prompt:
        analysis = raw.strip()
        snippet = extract_analysis_snippet(analysis)
        if drill_mode == "pov":
            image_prompt = (
                "A first-person point-of-view perspective looking outwards from the selected "
                f"region, photorealistic wide-angle view, showing the surroundings: {snippet}"
            )
        else:
            image_prompt = f"Detailed internal cross-section view of the selected region: {snippet}"
    elif not image_prompt:
        if drill_mode == "pov":
            image_prompt = (
                "A first-person point-of-view perspective looking outwards from: "
                f"{snippet}"
            )
        else:
            image_prompt = f"Detailed internal cross-section of: {snippet}"
    return analysis, image_prompt


class DrillAnalyzer:
    """3-input VLM drill analysis — global marker, local crop, 2-task prompt."""

    def __init__(self, app_settings: Settings) -> None:
        self._llm = LLMClient(app_settings)
        self._vision_model = app_settings.EXPLAINER_VISION_MODEL

    @staticmethod
    def _resize_for_vlm(img: Image.Image, max_size: int = 768) -> str:
        if img.mode != "RGB":
            img = img.convert("RGB")
        if max(img.size) > max_size:
            img = img.copy()
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def _build_prompt(
        self,
        *,
        label_hint: str | None = None,
        parent_context: dict | None = None,
        drill_mode: str = "inside",
        pov_context_kind: PovContextKind = "none",
    ) -> str:
        parts: list[str] = []
        if parent_context:
            meta = parent_context.get("metadata", parent_context)
            if isinstance(meta, dict):
                headline = meta.get("editorial_headline") or meta.get("object")
                if headline:
                    parts.append(f"Parent layer: {headline}")
                paragraph = meta.get("explainer_paragraph")
                if paragraph and drill_mode != "pov":
                    parts.append(f"Parent context: {paragraph}")
            ancestry = parent_context.get("ancestry_chain")
            if isinstance(ancestry, list) and ancestry:
                segments: list[str] = []
                for item in ancestry:
                    if isinstance(item, dict):
                        obj = item.get("object", "")
                        mode = item.get("drill_mode", "inside")
                        if obj:
                            segments.append(f"{obj} [{mode}]")
                    elif isinstance(item, str) and item.strip():
                        segments.append(f"{item.strip()} [inside]")
                if segments:
                    parts.append(f"Drill path: {' → '.join(segments)}")
        if label_hint:
            parts.append(_LABEL_HINT_PREFIX.format(label=label_hint))
        if drill_mode == "pov":
            if pov_context_kind == "segment":
                parts.append(_TWO_TASK_POV_PROMPT_SEGMENT)
            elif pov_context_kind == "wide":
                parts.append(_TWO_TASK_POV_PROMPT_WIDE)
            else:
                parts.append(_TWO_TASK_POV_PROMPT_GLOBAL_ONLY)
        else:
            parts.append(_TWO_TASK_PROMPT)
        return "\n".join(parts)

    def _describe_style_reference(self, scene_b64: str) -> str:
        """Extract palette, materials, and lighting from the global scene for POV continuity."""
        prompt = (
            "Describe the visual style, color palette, artistic medium, lighting, textures, "
            "and materials in this scene. Keep it concise (under 50 words). Focus only on "
            "visual aesthetic elements to guide an image generator to maintain perfect visual "
            "continuity. Do not mention any text, labels, or annotations."
        )
        try:
            return self._llm.chat_completion(
                self._vision_model,
                prompt,
                images=[scene_b64],
                temperature=0.1,
                timeout=120,
                num_predict=150,
            ).strip()
        except Exception as exc:
            logger.warning("Failed to generate style reference description: %s", exc)
            return ""

    def _run_dual_image_vlm(
        self,
        global_b64: str,
        context_b64: str | None,
        prompt: str,
        *,
        drill_mode: str = "inside",
        include_context: bool = True,
    ) -> str:
        images = [global_b64]
        if include_context and context_b64:
            images.append(context_b64)
        num_predict = 480 if drill_mode == "pov" else 400
        return self._llm.chat_completion(
            self._vision_model,
            prompt,
            images=images,
            temperature=0.1,
            timeout=300,
            num_predict=num_predict,
        )

    async def analyze_drill(
        self,
        global_b64: str,
        local_b64: str,
        *,
        label_hint: str | None = None,
        parent_context: dict | None = None,
        drill_mode: str = "inside",
        pov_context_kind: PovContextKind = "wide",
        style_scene_b64: str | None = None,
    ) -> dict[str, str]:
        del style_scene_b64  # style continuity is embedded in POV IMAGE_PROMPT (no extra VLM call)
        loop = asyncio.get_running_loop()
        prompt = self._build_prompt(
            label_hint=label_hint,
            parent_context=parent_context,
            drill_mode=drill_mode,
            pov_context_kind=pov_context_kind if drill_mode == "pov" else "none",
        )

        def run() -> str:
            try:
                global_img = Image.open(io.BytesIO(base64.b64decode(global_b64)))
                local_img = Image.open(io.BytesIO(base64.b64decode(local_b64)))
                resized_global = self._resize_for_vlm(global_img, max_size=768)
                resized_local = self._resize_for_vlm(local_img, max_size=1024)
            except Exception as resize_exc:
                logger.warning("Failed to resize images for VLM: %s", resize_exc)
                resized_global = global_b64
                resized_local = local_b64

            include_context = drill_mode != "pov" or pov_context_kind != "none"
            return self._run_dual_image_vlm(
                resized_global,
                resized_local,
                prompt,
                drill_mode=drill_mode,
                include_context=include_context if drill_mode == "pov" else True,
            )

        raw = await loop.run_in_executor(None, run)
        analysis, image_prompt = _parse_vlm_sections(raw, drill_mode=drill_mode)
        
        # Extract visual style description from the parent global scene for visual continuity!
        style_desc = ""
        try:
            def run_style():
                try:
                    global_img = Image.open(io.BytesIO(base64.b64decode(global_b64)))
                    resized_global = self._resize_for_vlm(global_img, max_size=768)
                    return self._describe_style_reference(resized_global)
                except Exception as e:
                    logger.warning("Failed to resize/describe style ref: %s", e)
                    return ""
            style_desc = await loop.run_in_executor(None, run_style)
        except Exception as style_exc:
            logger.warning("Style extraction failed: %s", style_exc)

        return {
            "analysis": analysis,
            "image_prompt": image_prompt,
            "global_b64": global_b64,
            "local_crop_b64": local_b64,
            "style_desc": style_desc,
        }
