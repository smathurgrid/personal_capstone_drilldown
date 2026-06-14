"""Resolves drill-down context from custom topics, vision models, or comparisons."""

import json

from backend.services.explainer.context_analyzer import ContextAnalyzer


class DrillContextResolver:
    """Selects how drill-down semantic context is produced before image generation."""

    def __init__(self, context_analyzer: ContextAnalyzer) -> None:
        self._analyzer = context_analyzer

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
        if custom_topic:
            return {
                "drill_topic": (
                    f"An extreme macro close-up of {custom_topic}, "
                    "focusing on textures and materials."
                ),
                "metadata": {
                    "object": custom_topic,
                    "editorial_headline": f"Drilling into: {custom_topic}",
                    "explainer_paragraph": f"Exploring {custom_topic} in detail.",
                },
                "input_prompt": f"Detail zoom of {custom_topic}",
                "raw_json": json.dumps({"object": custom_topic}),
            }, grounding_path

        if vision_model == "none":
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
                    "style": "Visual continuity from previous page",
                },
                "input_prompt": "N/A — vision skipped",
                "raw_json": "{}",
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

        return await self._analyzer.identify_drill_context(
            parent_path,
            x,
            y,
            model_key=vision_model,
            segment_path=grounding_path,
            parent_context=parent_context,
        )
