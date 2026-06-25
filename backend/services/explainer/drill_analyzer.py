"""Per-click dual-image VLM analysis (F3 + F4)."""

from __future__ import annotations

import asyncio
import base64
import io
import re
import logging

from PIL import Image

from backend.shared.config import Settings
from backend.shared.llm_client import LLMClient

logger = logging.getLogger(__name__)

_TWO_TASK_PROMPT = """You are an expert technical illustrator analyzing a drill-down selection.

You receive TWO images:
1. Full scene with a red circle marking WHERE the user clicked (global context).
2. Cropped close-up of the region under the click (local detail).

TASK 1 — ANALYSIS: Describe what was clicked and its role in the larger scene.
TASK 2 — IMAGE PROMPT: Write a detailed prompt for an image generation model to illustrate what is INSIDE that region (cross-section or internal view). No text in the generated image.

Respond in exactly this format:
ANALYSIS:
<your analysis text>

IMAGE_PROMPT:
<your generation prompt>"""

_TWO_TASK_POV_PROMPT = """You are an expert cinematic photographer and scene designer analyzing a drill-down selection.

You receive TWO images:
1. Full scene with a red circle marking WHERE the user clicked (global context).
2. Cropped close-up of the region under the click (local detail).

TASK 1 — ANALYSIS: Describe what was clicked, its precise physical location, and what the surrounding environment, room, or landscape would look like when looking OUTWARDS from exactly those coordinates. Be vivid, descriptive, and physically accurate.

TASK 2 — IMAGE PROMPT: Write an exceptionally long, hyper-detailed, and descriptive prompt (150-250 words) written in a prose style for a state-of-the-art image generator (like FLUX) to illustrate a first-person point-of-view (POV) perspective looking OUTWARDS from exactly this component's physical coordinates. 
The prompt MUST specify:
- SPATIAL GEOMETRY & COMPOSITION: Describe the wide 180-degree outward view from the clicked component. Specify what is immediately nearby (midground) and what is far away in the distance (background) to create massive depth.
- CRITICAL POV CAMERA ANCHORING RULE (PREVENT SUBJECT-CAMERA CONFUSION): Since the virtual camera is physically positioned ON or INSIDE the clicked component and looking OUTWARD, the clicked component itself MUST NOT be visible in the middle or background of the scene. For example, if you clicked on the 'Eiffel Tower', do NOT generate an image of the Eiffel Tower standing in front of you; instead, generate the sprawling panoramic Paris skyline and the Seine River seen *from* the tower's observation deck. If you clicked on a 'telescope lens', describe the night sky or distant stars as seen looking through the lens. The clicked component may only be visible as an extreme close-up framing element or soft out-of-focus bokeh blur along the very edges/borders of the frame to anchor the first-person perspective.
- TACTILE TEXTURES & MATERIALS: Describe every visible surface in exquisite, microscopic detail (e.g., oxidized copper, polished cherry wood with fine grain, matte carbon fiber, brushed stainless steel with micro-abrasions, dusty textured plaster, velvet fabric with delicate stitching).
- CINEMATIC LIGHTING & ATMOSPHERE: Describe how light behaves in the space (e.g., warm golden sunlight filtering through high windows casting long dramatic shadows and illuminating floating dust motes; cool neon ambient light reflecting off wet concrete; soft volumetric fog; realistic ray-traced ambient occlusion).
- COLOR PALETTE & MOOD: Specify the exact color grading, temperature, and atmospheric mood (e.g., cozy, futuristic, sterile, rustic, industrial).
- CRITICAL: No text, words, letters, labels, or annotations of any kind should be in the image.

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
    if not analysis and not image_prompt:
        analysis = raw.strip()
        if drill_mode == "pov":
            image_prompt = f"A first-person point-of-view perspective looking outwards from the selected region, photorealistic wide-angle view, showing the surroundings: {analysis[:200]}"
        else:
            image_prompt = f"Detailed internal cross-section view of the selected region: {analysis[:200]}"
    elif not image_prompt:
        if drill_mode == "pov":
            image_prompt = f"A first-person point-of-view perspective looking outwards from: {analysis[:200]}"
        else:
            image_prompt = f"Detailed internal cross-section of: {analysis[:200]}"
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
    ) -> str:
        parts: list[str] = []
        if parent_context:
            meta = parent_context.get("metadata", parent_context)
            if isinstance(meta, dict):
                headline = meta.get("editorial_headline") or meta.get("object")
                paragraph = meta.get("explainer_paragraph")
                if headline:
                    parts.append(f"Parent layer: {headline}")
                if paragraph:
                    parts.append(f"Parent context: {paragraph}")
        if label_hint:
            parts.append(_LABEL_HINT_PREFIX.format(label=label_hint))
        if drill_mode == "pov":
            parts.append(_TWO_TASK_POV_PROMPT)
        else:
            parts.append(_TWO_TASK_PROMPT)
        return "\n".join(parts)

    def _describe_style_reference(self, crop_b64: str) -> str:
        """Analyze local crop image to extract detailed style, colors, materials, and textures for continuity."""
        prompt = (
            "Describe the visual style, color palette, artistic medium, lighting, textures, "
            "and materials in this image. Keep it concise (under 50 words). Focus only on "
            "visual aesthetic elements to guide an image generator to maintain perfect visual "
            "continuity. Do not mention any text, labels, or annotations."
        )
        try:
            return self._llm.chat_completion(
                self._vision_model,
                prompt,
                images=[crop_b64],
                temperature=0.1,
                timeout=120,
                num_predict=150,
            ).strip()
        except Exception as exc:
            logger.warning("Failed to generate style reference description: %s", exc)
            return ""

    def _run_dual_image_vlm(self, global_b64: str, local_b64: str, prompt: str, max_tokens: int = 350) -> str:
        return self._llm.chat_completion(
            self._vision_model,
            prompt,
            images=[global_b64, local_b64],
            temperature=0.1,
            timeout=300,
            num_predict=max_tokens,
        )

    async def analyze_drill(
        self,
        global_b64: str,
        local_b64: str,
        *,
        label_hint: str | None = None,
        parent_context: dict | None = None,
        drill_mode: str = "inside",
    ) -> dict[str, str]:
        loop = asyncio.get_event_loop()
        prompt = self._build_prompt(
            label_hint=label_hint,
            parent_context=parent_context,
            drill_mode=drill_mode,
        )

        def run() -> tuple[str, str]:
            try:
                global_img = Image.open(io.BytesIO(base64.b64decode(global_b64)))
                local_img = Image.open(io.BytesIO(base64.b64decode(local_b64)))
                resized_global = self._resize_for_vlm(global_img)
                resized_local = self._resize_for_vlm(local_img)
            except Exception as resize_exc:
                logger.warning("Failed to resize images for VLM: %s", resize_exc)
                resized_global = global_b64
                resized_local = local_b64

            max_tokens = 800 if drill_mode == "pov" else 350
            raw = self._run_dual_image_vlm(resized_global, resized_local, prompt, max_tokens=max_tokens)
            style_desc = ""
            if drill_mode == "pov":
                style_desc = self._describe_style_reference(resized_local)
            return raw, style_desc

        raw, style_desc = await loop.run_in_executor(None, run)
        analysis, image_prompt = _parse_vlm_sections(raw, drill_mode=drill_mode)
        return {
            "analysis": analysis,
            "image_prompt": image_prompt,
            "global_b64": global_b64,
            "local_crop_b64": local_b64,
            "style_desc": style_desc,
        }
