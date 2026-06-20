"""VLM-backed next-region selection for F7 auto-drill."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import re

from PIL import Image

from backend.shared.config import Settings
from backend.shared.json_extractor import extract_json
from backend.shared.llm_client import LLMClient

_PICK_PROMPT = """You are guiding an educational semantic drill-down exploration.

Study this image and choose the SINGLE most valuable next region to drill into —
a sub-component that would be interesting to see the internal structure of.

Return ONLY a JSON object:
{
  "x": <normalized x 0.0-1.0>,
  "y": <normalized y 0.0-1.0>,
  "label": "<short name of the region>"
}

Pick a point at the visual center of the chosen component. Avoid edges and background."""


class RegionPicker:
    """Uses VLM intelligence to pick the next drill coordinate."""

    def __init__(self, app_settings: Settings) -> None:
        self._llm = LLMClient(app_settings)
        self._vision_model = app_settings.VISION_MODEL

    @staticmethod
    def _image_to_b64(image_bytes: bytes, max_size: int = 768) -> str:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("RGB")
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode("utf-8")

    def _run_pick_vlm(self, img_b64: str) -> str:
        return self._llm.chat_completion(
            self._vision_model,
            _PICK_PROMPT,
            images=[img_b64],
            temperature=0.2,
            timeout=180,
        )

    @staticmethod
    def _normalize_coord(val: float) -> float:
        if val > 1.0:
            return round(min(1.0, max(0.0, val / 1000.0)), 4)
        return round(min(1.0, max(0.0, val)), 4)

    def _parse_pick(self, raw: str, width: int, height: int) -> dict:
        try:
            data = json.loads(extract_json(raw))
            x = self._normalize_coord(float(data.get("x", 0.5)))
            y = self._normalize_coord(float(data.get("y", 0.5)))
            label = str(data.get("label", "region"))
            return {"x": x, "y": y, "label": label, "x_px": int(x * width), "y_px": int(y * height)}
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        nums = re.findall(r"0?\.\d+|\d+\.\d+|\d+", raw)
        if len(nums) >= 2:
            x = self._normalize_coord(float(nums[0]))
            y = self._normalize_coord(float(nums[1]))
            return {
                "x": x,
                "y": y,
                "label": "region",
                "x_px": int(x * width),
                "y_px": int(y * height),
            }
        return {"x": 0.5, "y": 0.5, "label": "center", "x_px": width // 2, "y_px": height // 2}

    async def pick_next_region(self, image_bytes: bytes) -> dict:
        loop = asyncio.get_event_loop()
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.convert("RGB").size

        img_b64 = self._image_to_b64(image_bytes)

        def run() -> str:
            return self._run_pick_vlm(img_b64)

        raw = await loop.run_in_executor(None, run)
        return self._parse_pick(raw, width, height)
