"""Bridge explainer vision output to image generation services."""

import logging
from pathlib import Path

from backend.core.protocols import ImageGenerator
from backend.shared.drill_mode import build_flux_prompt
from backend.shared.image_utils import b64_to_file, crop_norm_region, path_to_b64

logger = logging.getLogger(__name__)


async def generate_drill_image_to_file(
    drill_topic: str,
    output_path: str | Path,
    parent_path: str,
    x: float,
    y: float,
    segment_path: str | None = None,
    marked_path: str | None = None,
    crop_path: str | None = None,
    drill_mode: str = "inside",
    style_desc: str = "",
    *,
    image_generator: ImageGenerator,
) -> Path:
    """Generate a drill-down PNG and save it to disk."""
    del marked_path  # VLM-only marker image — never pass to generation

    # Clean parent scene for aesthetic continuity (no red click ring)
    global_b64 = path_to_b64(parent_path)

    if drill_mode == "pov":
        local_b64 = None
    elif segment_path and Path(segment_path).exists() and drill_mode != "pov":
        local_b64 = path_to_b64(segment_path)
    elif crop_path and Path(crop_path).exists():
        local_b64 = path_to_b64(crop_path)
    else:
        local_b64 = crop_norm_region(parent_path, x, y)

    enhanced_prompt = build_flux_prompt(
        drill_topic,
        drill_mode,
        style_desc=style_desc,
    )

    logger.info(
        "Flux generation drill_mode=%s prompt_len=%d",
        drill_mode,
        len(enhanced_prompt),
    )

    result = await image_generator.generate(
        prompt=enhanced_prompt,
        local_crop_b64=local_b64,
        global_b64=global_b64,
    )
    return b64_to_file(result["image_b64"], output_path)


async def generate_topic_image_to_file(
    topic: str,
    output_path: str | Path,
    *,
    image_generator: ImageGenerator,
) -> tuple[Path, str]:
    """Create the initial explainer page image from a text topic."""
    from backend.services.explainer.image_generator import generate_topic_image

    result = await generate_topic_image(topic, image_generator=image_generator)
    path = b64_to_file(result["image_b64"], output_path)
    return path, result.get("image_prompt", topic)
