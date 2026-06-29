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


def _loads_array(raw: str) -> list:
    """Parse a JSON array from model output (json_mode returns clean JSON).
    Local helper so we don't touch the shared object-only extract_json.

    Ollama's ``format:"json"`` forces a top-level OBJECT, so a prompt that asks for
    an array of N items usually comes back WRAPPED, e.g. ``{"components": [...]}``.
    We must unwrap that inner list — otherwise the whole object is treated as a
    single item and N collapses to 1."""
    if not raw:
        return []
    s = raw.strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", s, re.DOTALL)
    if m:
        s = m.group(1).strip()
    for candidate in (s, s[s.find("["): s.rfind("]") + 1] if "[" in s and "]" in s else ""):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Unwrap the first list value (the wrapped array); fall back to the
            # object itself as a single-item list only if it has no array field.
            for value in data.values():
                if isinstance(value, list):
                    return value
            return [data]
    return []

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


# --- Speculative drill prompts (ported) -------------------------------------------
_TOP_REGIONS_PROMPT = """You are guiding an educational semantic drill-down exploration.

Study this image and choose the {n} MOST valuable regions a curious user would most
likely want to drill into next — each a distinct sub-component. Order them by how
likely the user is to click, most likely first.

Return ONLY a JSON object whose "regions" array has EXACTLY {n} objects, ranked best-first:
{{"regions": [ {{"x": <0.0-1.0>, "y": <0.0-1.0>, "label": "<short name>"}} ]}}
The "regions" array MUST contain {n} items.

Each point at the visual center of its component; spatially distinct; avoid edges."""


_PREDICT_FROM_PROMPT = """A new image is about to be generated from this description:
"{child_prompt}"

That new image will be a detailed, zoomed-in / internal view. BEFORE it exists, predict the
{n} most interesting DISTINCT sub-components a curious user would drill into NEXT inside it,
ranked most-likely first.

For EACH component, write a vivid, specific image-generation prompt for the deeper zoomed-in /
internal / cross-section view of THAT component (name its materials, textures, parts and the
viewpoint). Make each clearly DISTINCT. No art style or text in the image.

Return ONLY a JSON object whose "components" array has EXACTLY {n} objects, best-first:
{{"components": [ {{"label": "<short component name>", "gen_prompt": "<detailed prompt>"}} ]}}
The "components" array MUST contain {n} items. Output JSON only."""


_LOCATE_PROMPT = """Find each of these components in the image and give its center point.
Components to find: {labels}

Return a JSON array with ONE object for EVERY component listed above — do not skip any.
For each, give your best-guess center even if the component is small, partially occluded, or
only loosely matches; pick the most plausible region rather than omitting it. Only set
"x" and "y" to null if the component is genuinely nowhere in the image.
[ {{"label": "<one of the components>", "x": <0.0-1.0 or null>, "y": <0.0-1.0 or null>}} ]
Coordinates normalized 0-1 at the visual center. Output JSON only."""


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
            num_predict=120,
            json_mode=True,
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

    # --- Speculative drill methods (ported) ---------------------------------------

    def _parse_top_regions(self, raw: str, width: int, height: int, n: int) -> list[dict]:
        regions: list[dict] = []
        try:
            data = _loads_array(raw)
            if isinstance(data, dict):
                data = [data]
            for rank, item in enumerate(data, start=1):
                x = self._normalize_coord(float(item.get("x", 0.5)))
                y = self._normalize_coord(float(item.get("y", 0.5)))
                regions.append({
                    "rank": rank, "x": x, "y": y,
                    "label": str(item.get("label", f"region {rank}")),
                    "x_px": int(x * width), "y_px": int(y * height),
                })
        except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
            regions = []
        if not regions:
            single = self._parse_pick(raw, width, height)
            single["rank"] = 1
            regions = [single]
        return regions[:n]

    async def pick_top_regions(self, image_bytes: bytes, n: int = 5) -> list[dict]:
        loop = asyncio.get_event_loop()
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.convert("RGB").size
        img_b64 = self._image_to_b64(image_bytes)

        def run() -> str:
            return self._llm.chat_completion(
                self._vision_model, _TOP_REGIONS_PROMPT.format(n=n),
                images=[img_b64], temperature=0.3, timeout=180,
                num_predict=400, json_mode=True,
            )

        raw = await loop.run_in_executor(None, run)
        return self._parse_top_regions(raw, width, height, n)

    def _parse_predicted_components(self, raw: str, n: int) -> list[dict]:
        out: list[dict] = []
        try:
            data = _loads_array(raw)
            if isinstance(data, dict):
                data = [data]
        except (json.JSONDecodeError, ValueError, TypeError):
            data = []
        for rank, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", f"component {rank}")).strip()
            gen = str(item.get("gen_prompt") or "").strip()
            if not label:
                continue
            if not gen:
                gen = f"Detailed zoomed-in internal view of the {label}, no text or labels."
            out.append({"rank": rank, "label": label, "gen_prompt": gen})
        return out[:n]

    async def predict_child_hotspots(
        self, child_prompt: str, parent_crop_b64: str | None = None, n: int = 5
    ) -> list[dict]:
        loop = asyncio.get_event_loop()
        images = [parent_crop_b64] if parent_crop_b64 else None

        def run() -> str:
            return self._llm.chat_completion(
                self._vision_model,
                _PREDICT_FROM_PROMPT.format(child_prompt=child_prompt or "the image", n=n),
                images=images, temperature=0.4, timeout=180,
                num_predict=500, json_mode=True,
            )

        raw = await loop.run_in_executor(None, run)
        return self._parse_predicted_components(raw, n)

    def _parse_located(self, raw: str, labels: list[str]) -> dict[str, list[float]]:
        try:
            data = _loads_array(raw)
            if isinstance(data, dict):
                data = [data]
        except (json.JSONDecodeError, ValueError, TypeError):
            data = []
        by_lower = {lbl.lower(): lbl for lbl in labels}
        found: dict[str, list[float]] = {}

        def _coords(item: dict) -> list[float] | None:
            """Return [x, y] only when BOTH are real numbers — never default to
            center, so a coordinate-less response can't pin a phantom marker at 0.5/0.5."""
            x_raw, y_raw = item.get("x"), item.get("y")
            if x_raw is None or y_raw is None:
                return None
            try:
                return [self._normalize_coord(float(x_raw)), self._normalize_coord(float(y_raw))]
            except (ValueError, TypeError):
                return None

        # Pass 1: exact label matches first, so fuzzy matching can't steal a label
        # that another entry names exactly.
        for item in data:
            if not isinstance(item, dict):
                continue
            match = by_lower.get(str(item.get("label", "")).strip().lower())
            if match is None or match in found:
                continue
            coords = _coords(item)
            if coords is not None:
                found[match] = coords

        # Pass 2: fuzzy (substring) matches for anything still unlocated.
        for item in data:
            if not isinstance(item, dict):
                continue
            raw_label = str(item.get("label", "")).strip().lower()
            if not raw_label:
                continue
            match = next(
                (orig for low, orig in by_lower.items()
                 if orig not in found and low and (low in raw_label or raw_label in low)),
                None,
            )
            if match is None:
                continue
            coords = _coords(item)
            if coords is not None:
                found[match] = coords
        return found

    async def locate_hotspots(
        self, child_image_bytes: bytes, labels: list[str]
    ) -> dict[str, list[float]]:
        if not labels:
            return {}
        loop = asyncio.get_event_loop()
        img_b64 = self._image_to_b64(child_image_bytes)

        def run() -> str:
            return self._llm.chat_completion(
                self._vision_model, _LOCATE_PROMPT.format(labels=", ".join(labels)),
                images=[img_b64], temperature=0.1, timeout=180,
                num_predict=300, json_mode=True,
            )

        raw = await loop.run_in_executor(None, run)
        return self._parse_located(raw, labels)
