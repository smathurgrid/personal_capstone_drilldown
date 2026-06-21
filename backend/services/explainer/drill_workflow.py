"""Shared explainer drill-down completion logic."""

from backend.core.protocols import ExplainerPageStore, ImageGenerator
from backend.shared.generation_bridge import generate_drill_image_to_file


def extract_vision_fields(vision_result: dict) -> tuple[str, dict, str, str]:
    drill_topic = vision_result.get("drill_topic", "a detailed sub-component")
    metadata = vision_result.get("metadata", {})
    input_prompt = vision_result.get("input_prompt", "")
    raw_json = vision_result.get("raw_json", vision_result.get("rawJson", ""))
    return drill_topic, metadata, input_prompt, raw_json


def build_result_metadata(
    drill_topic: str,
    metadata: dict,
    input_prompt: str,
    raw_json: str,
    sam_confidence: float | None,
    grounding_mode: str,
) -> dict:
    return {
        "context": drill_topic,
        "metadata": metadata,
        "inputPrompt": input_prompt,
        "rawJson": raw_json,
        "samConfidence": sam_confidence,
        "groundingMode": grounding_mode,
    }


class DrillWorkflow:
    def __init__(self, page_store: ExplainerPageStore, image_generator: ImageGenerator) -> None:
        self._pages = page_store
        self._image_generator = image_generator

    async def complete_drill(
        self,
        page_id: str,
        output_path: str,
        metadata_path: str,
        drill_topic: str,
        parent_path: str,
        x: float,
        y: float,
        segment_path: str | None,
        marked_path: str | None,
        crop_path: str | None,
        result_metadata: dict,
        drill_mode: str = "inside",
        style_desc: str = "",
    ) -> dict:
        await generate_drill_image_to_file(
            drill_topic,
            output_path,
            parent_path,
            x,
            y,
            segment_path=segment_path,
            marked_path=marked_path,
            crop_path=crop_path if isinstance(crop_path, str) else None,
            drill_mode=drill_mode,
            style_desc=style_desc,
            image_generator=self._image_generator,
        )
        self._pages.save_drill_metadata(metadata_path, result_metadata)
        self._pages.cleanup_temp_files(segment_path, marked_path, crop_path)
        return {"id": page_id, "imageUrl": self._pages.image_url(page_id), **result_metadata}
