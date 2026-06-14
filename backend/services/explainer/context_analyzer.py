"""Vision analysis for explainer — LiteLLM or Ollama."""

import asyncio
import base64
import io
import json
import traceback

from PIL import Image

from backend.shared.config import Settings
from backend.shared.json_extractor import extract_json
from backend.shared.llm_client import LLMClient, get_llm_client


class ContextAnalyzer:
    """Runs global and drill-down vision prompts against Ollama."""

    STRUCTURED_PROMPT = (
        "SYSTEM PERSONA: You are an expert Technical Forensic Analyst and Master Illustrator. "
        "You specialize in identifying complex internal structures for educational textbooks.\n\n"
        "TASK: Analyze the technical sub-component at the specified location. Identify its material composition, "
        "mechanical function, and internal layers.\n\n"
        "FIELDS TO FILL:\n"
        "1. 'object': Specific, granular technical name of the part.\n"
        "2. 'materials': List specific technical materials and textures.\n"
        "3. 'style': The design aesthetic.\n"
        "4. 'editorial_headline': A short technical title (max 6 words).\n"
        "5. 'explainer_paragraph': 2-3 sentences of technical context.\n"
        "6. 'drill_topic': MASTER IMAGE PROMPT for the next layer — educational illustration, no text in image.\n\n"
        "OUTPUT: Return ONLY a raw JSON object. No conversation."
    )

    GLOBAL_DETECTION_PROMPT = (
        "TASK: Forensic Scene Analysis.\n"
        "1. Create a technical 'editorial_headline' for the scene.\n"
        "2. Write a 2-sentence 'explainer_paragraph' summarizing the technology shown.\n"
        "3. Identify 8-10 major sub-components in 'granular_details'. Each MUST have: 'label', 'description', and 'point' [x, y].\n"
        "OUTPUT: Return ONLY a raw JSON object with these 3 root keys."
    )

    FOCUS_DETECTION_PROMPT = (
        "TASK: Local focus scan for a drilled/generated illustration.\n"
        "1. Create a short 'editorial_headline' for this zoomed view.\n"
        "2. Write one 'explainer_paragraph' sentence about what is visible.\n"
        "3. Identify 3-5 sub-parts near the image center in 'granular_details'. "
        "Each MUST have: 'label', 'description', and normalized 'point' [x, y] between 0 and 1.\n"
        "OUTPUT: Return ONLY a raw JSON object with these 3 root keys."
    )

    def __init__(self, app_settings: Settings) -> None:
        self._llm = LLMClient(app_settings)
        self._vision_model = app_settings.EXPLAINER_VISION_MODEL

    def _resolve_model(self, model_key: str) -> str | None:
        if model_key == "none":
            return None
        return self._vision_model

    @staticmethod
    def _normalize_scalar(val: float) -> float:
        if val > 2.0:
            return round(val / 1000.0, 4)
        return round(val, 4)

    @classmethod
    def _bbox_to_point(cls, bbox: list) -> list[float] | None:
        if not isinstance(bbox, list) or len(bbox) != 4:
            return None
        vals = [cls._normalize_scalar(float(v)) for v in bbox]
        a, b, c, d = vals
        candidates = [
            ((b + d) / 2.0, (a + c) / 2.0),
            ((a + c) / 2.0, (b + d) / 2.0),
        ]
        for cx, cy in candidates:
            if 0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0:
                return [round(cx, 4), round(cy, 4)]
        return None

    @classmethod
    def _sanitize_coordinates(cls, data):
        if isinstance(data, list):
            data = {"granular_details": data}
        if not isinstance(data, dict):
            return {"granular_details": []}

        for k_h in ["headline", "title", "subject", "topic"]:
            if k_h in data and "editorial_headline" not in data:
                data["editorial_headline"] = data[k_h]
        for k_e in ["description", "explainer", "summary", "context"]:
            if k_e in data and "explainer_paragraph" not in data:
                data["explainer_paragraph"] = data[k_e]
        if "name" in data and "object" not in data:
            data["object"] = data["name"]
        if "editorial_headline" not in data:
            data["editorial_headline"] = "Technical Component Analysis"
        if "explainer_paragraph" not in data:
            data["explainer_paragraph"] = "System-level forensic scan of the region."

        details = []
        if not any(k in data for k in ["granular_details", "details", "objects", "components", "items"]):
            for k, v in data.items():
                if isinstance(v, dict) and any(
                    pk in v for pk in ["label", "point", "center_point", "bbox_2d", "component"]
                ):
                    details.append(v)
        if not details:
            for key in ["granular_details", "details", "objects", "components", "items"]:
                if key in data and isinstance(data[key], list):
                    details = data[key]
                    break
        if not details:
            details = data.get("granular_details", [])
        data["granular_details"] = details

        for detail in details:
            if not isinstance(detail, dict):
                continue
            if "label" not in detail:
                detail["label"] = detail.get(
                    "component", detail.get("name", detail.get("object", "Technical Detail"))
                )
            if "description" not in detail:
                detail["description"] = detail.get(
                    "text", detail.get("explainer", detail.get("purpose", ""))
                )
            if "bbox_2d" in detail and isinstance(detail["bbox_2d"], list):
                bbox_point = cls._bbox_to_point(detail["bbox_2d"])
                if bbox_point:
                    detail["point"] = bbox_point
            if "point" not in detail:
                for k_p in ["centerPoint", "center_point", "center", "location"]:
                    if k_p in detail:
                        detail["point"] = detail[k_p]
                        break
            point = detail.get("point")
            if isinstance(point, list) and len(point) >= 2:
                normalized = [cls._normalize_scalar(float(point[0])), cls._normalize_scalar(float(point[1]))]
                if 0.0 <= normalized[0] <= 1.0 and 0.0 <= normalized[1] <= 1.0:
                    detail["point"] = normalized
                    detail.pop("position_uncertain", None)
                else:
                    detail.pop("point", None)
                    detail["position_uncertain"] = True
            else:
                detail.pop("point", None)
                detail["position_uncertain"] = True
        return data

    @staticmethod
    def _prepare_vision_image(image_path: str, max_size: int = 768) -> str:
        with Image.open(image_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _run_vision_chat(self, prompt: str, img_b64: str, *, timeout: int = 300) -> str:
        return self._llm.chat_completion(
            self._vision_model,
            prompt,
            images=[img_b64],
            temperature=0.0,
            timeout=timeout,
            think=False,
        )

    @staticmethod
    def _build_parent_context_block(parent_context: dict | None) -> str:
        if not parent_context:
            return ""
        meta = parent_context.get("metadata", parent_context)
        if not isinstance(meta, dict):
            return ""
        headline = meta.get("editorial_headline") or meta.get("object") or ""
        paragraph = meta.get("explainer_paragraph") or ""
        depth = parent_context.get("depth")
        parts = []
        if headline:
            parts.append(f"Parent layer headline: {headline}")
        if paragraph:
            parts.append(f"Parent context: {paragraph}")
        if depth is not None:
            parts.append(f"Drill depth: {int(depth) + 1}")
        if not parts:
            return ""
        return "\n".join(parts) + "\n\n"

    async def analyze_page(
        self,
        image_path: str,
        model_key: str = "qwen3.5",
        scan_mode: str = "global",
    ):
        model = self._resolve_model(model_key)
        if model is None:
            return {
                "metadata": {
                    "editorial_headline": "Vision skipped",
                    "granular_details": [],
                },
                "rawJson": "{}",
            }

        prompt = self.FOCUS_DETECTION_PROMPT if scan_mode == "focus" else self.GLOBAL_DETECTION_PROMPT
        loop = asyncio.get_event_loop()
        for attempt in range(2):
            try:
                img_b64 = self._prepare_vision_image(image_path)

                def run():
                    return self._run_vision_chat(prompt, img_b64)

                raw_text = await loop.run_in_executor(None, run)
                data = json.loads(extract_json(raw_text))
                result = self._sanitize_coordinates(data)
                if result.get("granular_details") or scan_mode == "focus":
                    return {"metadata": result, "rawJson": json.dumps(result, indent=2)}
            except Exception as exc:
                traceback.print_exc()
                if attempt == 1:
                    return {
                        "metadata": {"editorial_headline": "Error", "granular_details": []},
                        "rawJson": str(exc),
                    }
        return {
            "metadata": {"editorial_headline": "Empty Scan", "granular_details": []},
            "rawJson": "{}",
        }

    async def identify_drill_context(
        self,
        image_path: str,
        x: float,
        y: float,
        model_key: str = "qwen3.5",
        segment_path: str | None = None,
        parent_context: dict | None = None,
    ):
        loop = asyncio.get_event_loop()
        import os

        process_path = segment_path if segment_path and os.path.exists(segment_path) else image_path
        model = self._resolve_model(model_key)
        if model is None:
            return {
                "drill_topic": (
                    "a detailed macro-zoom into the textures and components of this specific area"
                ),
                "metadata": {
                    "object": "Undefined Component",
                    "editorial_headline": "The Pure Detail",
                    "explainer_paragraph": (
                        "Direct visual drill-down without semantic analysis. "
                        "Generation uses textures and shapes from the grounded region."
                    ),
                },
                "input_prompt": "N/A — vision skipped",
                "raw_json": "{}",
            }, process_path

        parent_block = self._build_parent_context_block(parent_context)
        click_block = f"Click location (normalized): x={round(x, 4)}, y={round(y, 4)}.\n\n"
        prompt = parent_block + click_block + self.STRUCTURED_PROMPT

        try:
            img_b64 = self._prepare_vision_image(process_path, max_size=800)

            def run():
                return self._run_vision_chat(prompt, img_b64)

            raw_text = await loop.run_in_executor(None, run)
            data = json.loads(extract_json(raw_text))
            result = self._sanitize_coordinates(data)
            drill_topic = result.get("drill_topic") or (
                f"An extreme macro close-up of {result.get('object', 'detail')}, technical style."
            )
            return {
                "drill_topic": drill_topic,
                "raw_json": json.dumps(result, indent=2),
                "rawJson": json.dumps(result, indent=2),
                "metadata": result,
                "input_prompt": prompt[:240],
            }, process_path
        except Exception as exc:
            traceback.print_exc()
            return {
                "drill_topic": "detail",
                "metadata": {"object": "Error"},
                "rawJson": str(exc),
                "input_prompt": "",
            }, process_path
