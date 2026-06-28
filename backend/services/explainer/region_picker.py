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


_TOP_REGIONS_PROMPT = """You are guiding an educational semantic drill-down exploration.

Study this image and choose the {n} MOST valuable regions a curious user would most
likely want to drill into next — each a distinct sub-component worth seeing the
internal structure of. Order them by how likely the user is to click, most likely first.

Return ONLY a JSON array of exactly {n} objects, ranked best-first:
[
  {{"x": <normalized x 0.0-1.0>, "y": <normalized y 0.0-1.0>, "label": "<short name>"}},
  ...
]

Each point must sit at the visual center of its component. The regions must be
spatially distinct (do not cluster them on the same spot). Avoid edges and background."""


# Approach 2: ONE VLM pass over the full image returns N hotspots, each already
# carrying a rich, image-grounded generation prompt. No per-hotspot crops/markers
# and no extra VLM calls at predict time.
_PREDICT_PROMPT = """You are powering a smooth, lag-free "drill-down" explorer. The user is
looking at this image and will click ONE region to zoom into its internal structure.

In a SINGLE pass, study the image and choose the {n} regions the user is most likely to
click, ranked most-likely first. For EACH region write a detailed image-generation prompt
that, grounded in what is actually visible here, describes the deeper/internal/cross-section
view that should appear when the user drills in.

Return ONLY a JSON array of exactly {n} objects, best-first:
[
  {{
    "label": "<short component name>",
    "x": <normalized center x 0.0-1.0>,
    "y": <normalized center y 0.0-1.0>,
    "bbox": [<x0>, <y0>, <x1>, <y1>],            // normalized 0.0-1.0, the region's box
    "attributes": ["<salient visible trait>", "..."],
    "gen_prompt": "<detailed, vivid prompt for generating the zoomed-in / internal view of THIS component, consistent with the image's style; no text or labels in the image>"
  }}
]

Rules: regions must be spatially distinct (do not cluster). Coordinates and bbox must be
normalized 0-1. gen_prompt must be specific to what is visible, not generic. Output JSON only."""


# Overlapped flow: predict the child's hotspots from the child's PROMPT, BEFORE the
# child image exists, so hotspot images can render in parallel with the child.
_PREDICT_FROM_PROMPT = """A new image is about to be generated from this description:
"{child_prompt}"

That new image will be a detailed, zoomed-in / internal view. BEFORE it exists, predict the
{n} sub-components a curious user is most likely to drill into NEXT inside that new image,
ranked most-likely first. Base it on the description and the reference crop provided.

For EACH predicted component, write a detailed image-generation prompt for the deeper
zoomed-in view of THAT component (same illustration style, no text or labels in the image).

Return ONLY a JSON array of exactly {n} objects, best-first:
[
  {{"label": "<short component name>", "gen_prompt": "<detailed prompt for the zoomed view of this component>"}}
]
Output JSON only."""


# After the child exists, locate the predicted components on it (coordinates only — fast).
_LOCATE_PROMPT = """Find each of these components in the image and give its center point.
Components to find: {labels}

Return ONLY a JSON array — one object per component you can ACTUALLY see (omit any that are
not visible):
[
  {{"label": "<one of the components above>", "x": <normalized 0.0-1.0>, "y": <normalized 0.0-1.0>}}
]
Coordinates normalized 0-1 at the visual center of the component. Output JSON only."""


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

    def _run_top_regions_vlm(self, img_b64: str, n: int) -> str:
        return self._llm.chat_completion(
            self._vision_model,
            _TOP_REGIONS_PROMPT.format(n=n),
            images=[img_b64],
            temperature=0.3,
            timeout=180,
        )

    def _run_predict_vlm(self, img_b64: str, n: int) -> str:
        return self._llm.chat_completion(
            self._vision_model,
            _PREDICT_PROMPT.format(n=n),
            images=[img_b64],
            temperature=0.3,
            timeout=240,
        )

    def _bbox_from_center(self, x: float, y: float, half: float = 0.12) -> list[float]:
        """Fallback bbox around a center point when the VLM omits one."""
        return [
            round(max(0.0, x - half), 4),
            round(max(0.0, y - half), 4),
            round(min(1.0, x + half), 4),
            round(min(1.0, y + half), 4),
        ]

    def _parse_hotspots(self, raw: str, width: int, height: int, n: int) -> list[dict]:
        """Parse the enriched JSON array of hotspots; tolerant of missing fields."""
        hotspots: list[dict] = []
        try:
            data = json.loads(extract_json(raw, expect="array"))
            if isinstance(data, dict):
                data = [data]
        except (json.JSONDecodeError, ValueError, TypeError):
            data = []

        for rank, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                continue
            x = self._normalize_coord(float(item.get("x", 0.5)))
            y = self._normalize_coord(float(item.get("y", 0.5)))
            label = str(item.get("label", f"region {rank}"))

            bbox_raw = item.get("bbox")
            if isinstance(bbox_raw, (list, tuple)) and len(bbox_raw) == 4:
                bbox = [self._normalize_coord(float(v)) for v in bbox_raw]
            else:
                bbox = self._bbox_from_center(x, y)

            attributes = item.get("attributes")
            if not isinstance(attributes, list):
                attributes = []
            attributes = [str(a) for a in attributes][:6]

            gen_prompt = str(item.get("gen_prompt") or "").strip()
            if not gen_prompt:
                # Fallback: synthesize a usable prompt from label + attributes.
                attr_text = (", " + ", ".join(attributes)) if attributes else ""
                gen_prompt = (
                    f"Detailed zoomed-in internal view of the {label}{attr_text}, "
                    f"educational illustration, clean style, no text or labels."
                )

            hotspots.append(
                {
                    "rank": rank,
                    "x": x,
                    "y": y,
                    "x_px": int(x * width),
                    "y_px": int(y * height),
                    "bbox": bbox,
                    "label": label,
                    "attributes": attributes,
                    "gen_prompt": gen_prompt,
                }
            )

        if not hotspots:
            # Last-resort fallback so the loop never dead-ends.
            single = self._parse_pick(raw, width, height)
            x, y = single["x"], single["y"]
            hotspots = [
                {
                    "rank": 1,
                    "x": x,
                    "y": y,
                    "x_px": int(x * width),
                    "y_px": int(y * height),
                    "bbox": self._bbox_from_center(x, y),
                    "label": single.get("label", "region"),
                    "attributes": [],
                    "gen_prompt": (
                        f"Detailed zoomed-in internal view of the {single.get('label', 'region')}, "
                        f"educational illustration, clean style, no text or labels."
                    ),
                }
            ]
        return hotspots[:n]

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

    def _parse_top_regions(self, raw: str, width: int, height: int, n: int) -> list[dict]:
        """Parse a ranked JSON array of regions; fall back to a single pick."""
        regions: list[dict] = []
        try:
            data = json.loads(extract_json(raw, expect="array"))
            if isinstance(data, dict):
                data = [data]
            for rank, item in enumerate(data, start=1):
                x = self._normalize_coord(float(item.get("x", 0.5)))
                y = self._normalize_coord(float(item.get("y", 0.5)))
                label = str(item.get("label", f"region {rank}"))
                regions.append(
                    {
                        "rank": rank,
                        "x": x,
                        "y": y,
                        "label": label,
                        "x_px": int(x * width),
                        "y_px": int(y * height),
                    }
                )
        except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
            regions = []

        if not regions:
            single = self._parse_pick(raw, width, height)
            single["rank"] = 1
            regions = [single]
        return regions[:n]

    async def pick_next_region(self, image_bytes: bytes) -> dict:
        loop = asyncio.get_event_loop()
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.convert("RGB").size

        img_b64 = self._image_to_b64(image_bytes)

        def run() -> str:
            return self._run_pick_vlm(img_b64)

        raw = await loop.run_in_executor(None, run)
        return self._parse_pick(raw, width, height)

    async def pick_top_regions(self, image_bytes: bytes, n: int = 5) -> list[dict]:
        """Rank the top-N drill regions in one VLM call (best-first)."""
        loop = asyncio.get_event_loop()
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.convert("RGB").size

        img_b64 = self._image_to_b64(image_bytes)

        def run() -> str:
            return self._run_top_regions_vlm(img_b64, n)

        raw = await loop.run_in_executor(None, run)
        return self._parse_top_regions(raw, width, height, n)

    async def predict_hotspots(self, image_bytes: bytes, n: int = 5) -> list[dict]:
        """Approach 2: one VLM pass → N enriched hotspots with image-grounded gen prompts."""
        loop = asyncio.get_event_loop()
        with Image.open(io.BytesIO(image_bytes)) as img:
            width, height = img.convert("RGB").size

        img_b64 = self._image_to_b64(image_bytes)

        def run() -> str:
            return self._run_predict_vlm(img_b64, n)

        raw = await loop.run_in_executor(None, run)
        return self._parse_hotspots(raw, width, height, n)

    # ----- Overlapped flow: predict-before-child, then locate-after-child -------

    def _parse_predicted_components(self, raw: str, n: int) -> list[dict]:
        """Parse [{label, gen_prompt}] predicted from the child's text prompt."""
        out: list[dict] = []
        try:
            data = json.loads(extract_json(raw, expect="array"))
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
                gen = (
                    f"Detailed zoomed-in internal view of the {label}, "
                    f"educational illustration, clean style, no text or labels."
                )
            out.append({"rank": rank, "label": label, "gen_prompt": gen})
        return out[:n]

    async def predict_child_hotspots(
        self, child_prompt: str, parent_crop_b64: str | None = None, n: int = 5
    ) -> list[dict]:
        """Predict the child's hotspots from its PROMPT, before the child is drawn."""
        loop = asyncio.get_event_loop()
        images = [parent_crop_b64] if parent_crop_b64 else None

        def run() -> str:
            return self._llm.chat_completion(
                self._vision_model,
                _PREDICT_FROM_PROMPT.format(child_prompt=child_prompt or "the image", n=n),
                images=images,
                temperature=0.4,
                timeout=180,
            )

        raw = await loop.run_in_executor(None, run)
        return self._parse_predicted_components(raw, n)

    def _parse_located(self, raw: str, labels: list[str]) -> dict[str, list[float]]:
        """Match VLM-returned positions back to the requested labels (fuzzy)."""
        try:
            data = json.loads(extract_json(raw, expect="array"))
            if isinstance(data, dict):
                data = [data]
        except (json.JSONDecodeError, ValueError, TypeError):
            data = []
        by_lower = {lbl.lower(): lbl for lbl in labels}
        found: dict[str, list[float]] = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            raw_label = str(item.get("label", "")).strip().lower()
            match = by_lower.get(raw_label)
            if match is None:
                for low, orig in by_lower.items():
                    if low and (low in raw_label or raw_label in low):
                        match = orig
                        break
            if match is None or match in found:
                continue
            x = self._normalize_coord(float(item.get("x", 0.5)))
            y = self._normalize_coord(float(item.get("y", 0.5)))
            found[match] = [x, y]
        return found

    async def locate_hotspots(
        self, child_image_bytes: bytes, labels: list[str]
    ) -> dict[str, list[float]]:
        """Find the given labels in the child image; return {label: [x, y]} (fast)."""
        if not labels:
            return {}
        loop = asyncio.get_event_loop()
        img_b64 = self._image_to_b64(child_image_bytes)
        labels_str = ", ".join(labels)

        def run() -> str:
            return self._llm.chat_completion(
                self._vision_model,
                _LOCATE_PROMPT.format(labels=labels_str),
                images=[img_b64],
                temperature=0.1,
                timeout=180,
            )

        raw = await loop.run_in_executor(None, run)
        return self._parse_located(raw, labels)
