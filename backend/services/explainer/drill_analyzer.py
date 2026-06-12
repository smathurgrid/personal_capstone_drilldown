"""Per-click dual-image VLM analysis (F3 + F4)."""

from __future__ import annotations

import asyncio
import base64
import io
import re

import requests
from PIL import Image

from backend.shared.config import Settings

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


def _parse_vlm_sections(raw: str) -> tuple[str, str]:
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
        image_prompt = f"Detailed internal cross-section view of the selected region: {analysis[:200]}"
    elif not image_prompt:
        image_prompt = f"Detailed internal cross-section of: {analysis[:200]}"
    return analysis, image_prompt


class DrillAnalyzer:
    """3-input VLM drill analysis — global marker, local crop, 2-task prompt."""

    def __init__(self, app_settings: Settings) -> None:
        self._ollama_url = app_settings.OLLAMA_BASE.rstrip("/") + "/api"
        self._vision_model = app_settings.VISION_MODEL

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

    def _run_dual_image_vlm(self, global_b64: str, local_b64: str) -> str:
        payload = {
            "model": self._vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": _TWO_TASK_PROMPT,
                    "images": [global_b64, local_b64],
                }
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        resp = requests.post(f"{self._ollama_url}/chat", json=payload, timeout=300)
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    async def analyze_drill(
        self,
        global_b64: str,
        local_b64: str,
    ) -> dict[str, str]:
        loop = asyncio.get_event_loop()

        def run() -> str:
            return self._run_dual_image_vlm(global_b64, local_b64)

        raw = await loop.run_in_executor(None, run)
        analysis, image_prompt = _parse_vlm_sections(raw)
        return {
            "analysis": analysis,
            "image_prompt": image_prompt,
            "global_b64": global_b64,
            "local_crop_b64": local_b64,
        }
