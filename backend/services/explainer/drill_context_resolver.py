"""Resolves drill-down context from custom topics, vision models, or comparisons."""

from __future__ import annotations

import io
import json
from pathlib import Path

from PIL import Image

from backend.services.explainer.context_analyzer import ContextAnalyzer
from backend.services.explainer.drill_analyzer import DrillAnalyzer
from backend.shared.image_utils import path_to_b64, prepare_drill_surfaces


class DrillContextResolver:
    """Selects how drill-down semantic context is produced before image generation."""

    def __init__(
        self,
        context_analyzer: ContextAnalyzer,
        drill_analyzer: DrillAnalyzer,
    ) -> None:
        self._analyzer = context_analyzer
        self._drill_analyzer = drill_analyzer

    @staticmethod
    def _read_parent_bytes(parent_path: str) -> tuple[bytes, int, int]:
        raw = Path(parent_path).read_bytes()
        with Image.open(io.BytesIO(raw)) as img:
            w, h = img.size
        return raw, w, h

    @staticmethod
    def _dual_result_to_vision(
        result: dict[str, str],
        *,
        label_hint: str | None = None,
        parent_context: dict | None = None,
    ) -> dict:
        analysis = result.get("analysis", "")
        image_prompt = result.get("image_prompt", "")
        object_name = label_hint or ""
        if not object_name and analysis:
            object_name = analysis.split(".")[0][:80].strip()
        if not object_name:
            object_name = "Selected component"

        headline = f"Drilling into: {object_name}"
        if parent_context:
            parent_meta = parent_context.get("metadata", parent_context)
            if isinstance(parent_meta, dict):
                parent_obj = parent_meta.get("object") or parent_meta.get("editorial_headline")
                if parent_obj:
                    headline = f"{parent_obj} → {object_name}"

        metadata = {
            "object": object_name,
            "editorial_headline": headline,
            "explainer_paragraph": analysis,
            "drill_topic": image_prompt,
        }
        return {
            "drill_topic": image_prompt,
            "metadata": metadata,
            "input_prompt": "dual-image drill analysis",
            "raw_json": json.dumps(
                {"object": object_name, "analysis": analysis, "drill_topic": image_prompt},
                indent=2,
            ),
            "global_b64": result.get("global_b64"),
            "local_crop_b64": result.get("local_crop_b64"),
            "crop_preview_b64": result.get("local_crop_b64"),
        }

    async def _resolve_dual_image(
        self,
        parent_path: str,
        x: float,
        y: float,
        *,
        label_hint: str | None = None,
        parent_context: dict | None = None,
    ) -> tuple[dict, None]:
        raw, w, h = self._read_parent_bytes(parent_path)
        x_px = int(x * w)
        y_px = int(y * h)
        global_b64, local_b64, _, _ = prepare_drill_surfaces(raw, x_px, y_px, 80)
        result = await self._drill_analyzer.analyze_drill(
            global_b64,
            local_b64,
            label_hint=label_hint,
            parent_context=parent_context,
        )
        return self._dual_result_to_vision(
            result,
            label_hint=label_hint,
            parent_context=parent_context,
        ), None

    async def resolve(
        self,
        parent_path: str,
        x: float,
        y: float,
        vision_model: str,
        grounding_mode: str,
        grounding_path: str | None,
        custom_topic: str | None,
        parent_context: dict | None = None,
    ):
        if vision_model == "none":
            crop_b64 = path_to_b64(parent_path)
            try:
                raw, w, h = self._read_parent_bytes(parent_path)
                x_px, y_px = int(x * w), int(y * h)
                _, local_b64, _, _ = prepare_drill_surfaces(raw, x_px, y_px, 80)
                crop_b64 = local_b64
            except OSError:
                pass
            return {
                "drill_topic": (
                    "a detailed macro-zoom into the textures and components of this specific area"
                ),
                "metadata": {
                    "object": custom_topic or "Undefined Component",
                    "editorial_headline": "The Pure Detail",
                    "explainer_paragraph": (
                        "Direct visual drill-down without semantic analysis. "
                        "Generation uses textures and shapes from the grounded region."
                    ),
                    "style": "Visual continuity from previous page",
                },
                "input_prompt": "N/A — vision skipped",
                "raw_json": "{}",
                "crop_preview_b64": crop_b64,
            }, None

        if vision_model == "all":
            models_to_test = ["qwen3.5"]
            results = []
            for model_key in models_to_test:
                try:
                    res, _ = await self._analyzer.identify_drill_context(
                        parent_path, x, y, model_key=model_key, segment_path=grounding_path
                    )
                    results.append(
                        {
                            "model": model_key,
                            "metadata": res.get("metadata", {}),
                            "rawJson": res.get("raw_json", ""),
                        }
                    )
                except Exception as exc:
                    results.append(
                        {"model": model_key, "metadata": {"error": str(exc)}, "rawJson": ""}
                    )
            return {"isComparison": True, "results": results, "groundingMode": grounding_mode}, None

        if custom_topic:
            return await self._resolve_dual_image(
                parent_path,
                x,
                y,
                label_hint=custom_topic,
                parent_context=parent_context,
            )

        return await self._resolve_dual_image(
            parent_path,
            x,
            y,
            parent_context=parent_context,
        )
