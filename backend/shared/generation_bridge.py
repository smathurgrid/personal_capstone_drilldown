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
    drill_mode: str = "inside",
    style_desc: str = "",
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

    if drill_mode == "pov":
        enhanced_prompt = (
            f"An absolute masterpiece, hyper-realistic, photorealistic first-person point-of-view (POV) photograph "
            f"shot on a premium full-frame Hasselblad camera with an ultra-wide 18mm prime lens at f/2.8, rendering "
            f"in clean, pristine, native 8k resolution. The camera is physically anchored exactly at the coordinates of the "
            f"clicked component, peering OUTWARD into the surrounding room and space.\n"
            f"Spatial Composition & Framing: The frame utilizes a wide 180-degree field of view with cinematic proportions. "
            f"The immediate, extreme close-up foreground edges catch the out-of-focus physical structure and framing outline of "
            f"the clicked object (rendering it in a beautiful, soft, out-of-focus bokeh blur), anchoring the camera's spatial presence "
            f"and providing an intense sense of physical scale.\n"
            f"Detailed Environment & Scenery: {drill_topic.strip()}\n"
            f"Cinematic Lighting & Atmosphere: Dramatic volumetric lighting, realistic ambient occlusion, and natural light bounces. "
            f"Rich, balanced color grading with deep shadows, clean balanced highlights, and cinematic color contrast matching a movie still.\n"
            f"Camera Settings: 1/125s shutter speed, ISO 100, award-winning architectural and technical photography style, completely free of any CGI, digital illustration, text, labels, or rendering look."
        )
        if style_desc:
            enhanced_prompt += (
                f"\nVisual Continuity Profile: To preserve perfect aesthetic alignment and visual continuity, the image MUST "
                f"strictly incorporate the following visual style, colors, materials, and atmosphere: {style_desc.strip()}."
            )
    else:
        enhanced_prompt = drill_topic

    if drill_mode == "pov":
        # For POV mode, we are looking outward from the object's perspective.
        # Passing the cropped object as an input image constraint is fundamentally incorrect and actively ruins the generation,
        # because it forces the outward-looking scene to visually look like the cropped object (due to img2img constraints).
        # Therefore, we pass None to ensure FLUX does pure text-to-image generation based strictly on our rich, detailed POV prompt.
        result = await image_generator.generate(
            prompt=enhanced_prompt,
            local_crop_b64=None,
            global_b64=None,
        )
    else:
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
