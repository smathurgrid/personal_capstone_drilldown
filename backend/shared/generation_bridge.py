"""Bridge explainer vision output to image generation services."""

import logging
from pathlib import Path

from backend.core.protocols import ImageGenerator
from backend.shared.image_utils import b64_to_file, crop_norm_region, draw_red_ring_b64, path_to_b64

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
    *,
    image_generator: ImageGenerator,
) -> Path:
    """Generate a drill-down PNG and save it to disk."""
    if segment_path and Path(segment_path).exists():
        local_b64 = path_to_b64(segment_path)
    elif crop_path and Path(crop_path).exists():
        local_b64 = path_to_b64(crop_path)
    else:
        local_b64 = crop_norm_region(parent_path, x, y)

    if marked_path and Path(marked_path).exists():
        global_b64 = path_to_b64(marked_path)
    else:
        global_b64 = draw_red_ring_b64(parent_path, x, y)

    result = await image_generator.generate(
        prompt=drill_topic,
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
