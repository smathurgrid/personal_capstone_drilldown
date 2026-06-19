import base64
import json
import re
import uuid
from typing import Any, Dict, List

import httpx
from PIL import Image

from ..core.config import settings


class VisionService:
    def __init__(self):
        self.model = settings.OLLAMA_VISION_MODEL
        self.host = settings.OLLAMA_HOST.rstrip("/")

    async def _generate_json(self, image_path: str, prompt: str) -> Dict[str, Any]:
        with open(image_path, "rb") as image_file:
            image_b64 = base64.b64encode(image_file.read()).decode("utf-8")

        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_ctx": 32768,
            },
        }

        last_exc: Exception | None = None
        for attempt in range(1, 3):
            try:
                async with httpx.AsyncClient(timeout=240.0) as client:
                    response = await client.post(f"{self.host}/api/generate", json=payload)
                    response.raise_for_status()
                content = response.json().get("response", "{}")
                return self._parse_json(content)
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                print(f"Ollama attempt {attempt} failed: {exc}. Retrying…")
                last_exc = exc
            except json.JSONDecodeError as exc:
                # Bad JSON from model — no point retrying
                raise RuntimeError(f"Model returned unparseable JSON: {exc}") from exc

        raise RuntimeError(f"Ollama unreachable after retries: {last_exc}") from last_exc

    def _parse_json(self, content: str) -> Dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?", "", content).strip()
            content = re.sub(r"```$", "", content).strip()

        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return {"garments": parsed}
            return parsed
        except json.JSONDecodeError:
            # Try recovering from a truncated garments array: strip the
            # incomplete last object and close the structure.
            last_complete = content.rfind("},")
            if last_complete > 0:
                candidate = content[: last_complete + 1]
                # Find the opening of the array to rewrap
                array_start = candidate.find("[")
                if array_start >= 0:
                    prefix = candidate[:array_start + 1]
                    items = candidate[array_start + 1:]
                    for suffix in ("]}", "]"):
                        try:
                            recovered = json.loads(prefix + items + suffix)
                            print(f"Recovered partial JSON (truncated response).")
                            if isinstance(recovered, list):
                                return {"garments": recovered}
                            return recovered
                        except json.JSONDecodeError:
                            pass

            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

    def _coerce_box(self, box: Dict[str, Any], width: int, height: int) -> Dict[str, int]:
        def clamp(value: Any, upper: int) -> int:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = 0
            if 0 <= numeric <= 1:
                numeric *= upper
            return max(0, min(int(round(numeric)), upper))

        x1 = clamp(box.get("x1", 0), width)
        y1 = clamp(box.get("y1", 0), height)
        x2 = clamp(box.get("x2", width), width)
        y2 = clamp(box.get("y2", height), height)

        if x2 <= x1:
            x2 = min(width, x1 + 1)
        if y2 <= y1:
            y2 = min(height, y1 + 1)

        return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}

    def _coerce_point(self, point: Dict[str, Any], fallback_box: Dict[str, int], width: int, height: int) -> Dict[str, int]:
        def clamp(value: Any, upper: int) -> int:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = -1
            if 0 <= numeric <= 1:
                numeric *= upper
            if numeric < 0:
                return -1
            return max(0, min(int(round(numeric)), upper))

        x = clamp(point.get("x"), width) if isinstance(point, dict) else -1
        y = clamp(point.get("y"), height) if isinstance(point, dict) else -1

        if x < 0:
            x = int(round((fallback_box["x1"] + fallback_box["x2"]) / 2))
        if y < 0:
            y = int(round((fallback_box["y1"] + fallback_box["y2"]) / 2))

        return {"x": x, "y": y}

    async def detect_garments(self, image_path: str) -> List[Dict[str, Any]]:
        with Image.open(image_path) as img:
            width, height = img.size

        prompt = f"""
Analyze the full outfit image and detect every clearly visible garment and accessory.
Include outerwear, shirts, tops, pants, jeans, skirts, dresses, shoes, eyewear, watches, jewelry, bags, belts, hats, and scarves.

Return ONLY valid JSON — no extra text before or after:
{{
  "garments": [
    {{
      "id": "g1",
      "label": "concise label e.g. Navy Blazer",
      "boundingBox": {{"x1": 0, "y1": 0, "x2": 0, "y2": 0}}
    }}
  ]
}}

Bounding boxes are absolute pixel coordinates for the {width}x{height} image.
Keep labels short (2-4 words). Do not include body parts or background objects.
"""

        data = await self._generate_json(image_path, prompt)
        raw_garments = data.get("garments", [])
        garments: List[Dict[str, Any]] = []

        for index, item in enumerate(raw_garments):
            box = item.get("boundingBox") or item.get("bounding_box") or {}
            normalized_box = self._coerce_box(box, width, height)
            label = str(item.get("label") or item.get("category") or f"Garment {index + 1}").strip()
            anchor = {
                "x": int(round((normalized_box["x1"] + normalized_box["x2"]) / 2)),
                "y": int(round((normalized_box["y1"] + normalized_box["y2"]) / 2)),
            }
            garment = {
                "id": str(item.get("id") or f"g{index + 1}-{uuid.uuid4().hex[:4]}"),
                "label": label[:60],
                "anchorPoint": anchor,
                "boundingBox": normalized_box,
                "description": str(item.get("description") or "").strip()[:160],
            }
            garments.append(garment)

        print("Detected garments:")
        for garment in garments:
            print(f"  {garment['id']} | {garment['label']} | point={garment['anchorPoint']} box={garment['boundingBox']}")

        return garments

    async def analyze_garment(self, image_path: str, bbox: Dict[str, Any]) -> Dict[str, Any]:
        with Image.open(image_path) as img:
            width, height = img.size
        box = self._coerce_box(bbox, width, height)

        prompt = f"""
Analyze only the garment or accessory inside this bounding box: {json.dumps(box)}.

Return only valid JSON in this exact shape:
{{
  "attributes": {{
    "category": "",
    "color": "",
    "material": "",
    "fit": "",
    "pattern": "",
    "style": "",
    "gender": "",
    "description": "",
    "confidence": ""
  }},
  "shopping_query": "optimized concise shopping query"
}}

The shopping query should be suitable for Google Shopping, for example:
"men navy oversized wool blazer".
"""

        data = await self._generate_json(image_path, prompt)
        attributes = data.get("attributes") or data
        normalized = {
            "category": str(attributes.get("category", "")).strip(),
            "color": str(attributes.get("color", "")).strip(),
            "material": str(attributes.get("material", "")).strip(),
            "fit": str(attributes.get("fit", "")).strip(),
            "pattern": str(attributes.get("pattern", "")).strip(),
            "style": str(attributes.get("style", "")).strip(),
            "gender": str(attributes.get("gender", "")).strip(),
            "description": str(attributes.get("description", "")).strip(),
            "confidence": str(attributes.get("confidence", "")).strip(),
        }

        query = str(data.get("shopping_query") or "").strip()
        if not query:
            query = " ".join(
                part
                for part in [
                    normalized["gender"],
                    normalized["color"],
                    normalized["fit"],
                    normalized["material"],
                    normalized["category"],
                ]
                if part
            )

        print(f"Garment details: {json.dumps(normalized, ensure_ascii=False)}")
        print(f"Generated shopping query: {query}")
        return {"attributes": normalized, "shopping_query": query}


vision_service = VisionService()
