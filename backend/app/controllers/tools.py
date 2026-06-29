"""Layer 3 tool handlers — shared by HTTP routes and pi-agent tools."""

from __future__ import annotations

import base64
import io

from fastapi import HTTPException, UploadFile
from PIL import Image

from backend.core.protocols import ImageGenerator
from backend.services.explainer.drill_analyzer import DrillAnalyzer
from backend.services.explainer.image_generator import generate_from_text
from backend.services.explainer.region_picker import RegionPicker
from backend.shared.config import settings
from backend.shared.image_utils import prepare_drill_surfaces


def _drill_analyzer() -> DrillAnalyzer:
    return DrillAnalyzer(settings)


def _region_picker() -> RegionPicker:
    return RegionPicker(settings)


async def handle_analyze_click(
    image: UploadFile,
    x: float,
    y: float,
    radius: float = 80,
) -> dict:
    """F3+F4: FormData image + pixel click → dual-image VLM analysis."""
    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail="image required")

    global_b64, local_b64, width, height = prepare_drill_surfaces(
        content, int(x), int(y), int(radius)
    )
    result = await _drill_analyzer().analyze_drill(global_b64, local_b64)
    return {
        "analysis": result["analysis"],
        "image_prompt": result["image_prompt"],
        "global_b64": result["global_b64"],
        "local_crop_b64": result["local_crop_b64"],
        "width": width,
        "height": height,
        "x": x,
        "y": y,
    }


async def handle_analyze_b64(body: dict) -> dict:
    """Analyze from base64 parent image + normalized coordinates."""
    image_b64 = body.get("image_b64") or body.get("parent_image_b64")
    if not image_b64:
        raise HTTPException(status_code=400, detail="image_b64 required")

    x_norm = float(body.get("x", 0.5))
    y_norm = float(body.get("y", 0.5))
    radius = int(body.get("radius", 80))

    raw = base64.b64decode(image_b64)
    with Image.open(io.BytesIO(raw)) as img:
        w, h = img.size
    x_px = int(x_norm * w)
    y_px = int(y_norm * h)

    global_b64, local_b64, width, height = prepare_drill_surfaces(raw, x_px, y_px, radius)
    result = await _drill_analyzer().analyze_drill(global_b64, local_b64)
    return {
        "analysis": result["analysis"],
        "image_prompt": result["image_prompt"],
        "global_b64": result["global_b64"],
        "local_crop_b64": result["local_crop_b64"],
        "width": width,
        "height": height,
        "x": x_norm,
        "y": y_norm,
    }


async def handle_pick_next_region(body: dict) -> dict:
    """F7 step 1: VLM picks next drill point on parent image."""
    image_b64 = body.get("image_b64") or body.get("parent_image_b64")
    if not image_b64:
        raise HTTPException(status_code=400, detail="image_b64 required")
    image_bytes = base64.b64decode(image_b64)
    return await _region_picker().pick_next_region(image_bytes)


# --- Speculative drill handlers (ported, additive) ------------------------------
async def handle_pick_top_regions(body: dict) -> dict:
    """Rank the top-N drill regions in one VLM call."""
    image_b64 = body.get("image_b64") or body.get("parent_image_b64")
    if not image_b64:
        raise HTTPException(status_code=400, detail="image_b64 required")
    n = int(body.get("n", 5))
    regions = await _region_picker().pick_top_regions(base64.b64decode(image_b64), n=n)
    return {"regions": regions}


async def handle_predict_child_hotspots(body: dict) -> dict:
    """Predict the child's hotspots from its PROMPT (no child image yet)."""
    n = int(body.get("n", 5))
    hotspots = await _region_picker().predict_child_hotspots(
        str(body.get("child_prompt", "")),
        parent_crop_b64=body.get("parent_crop_b64"),
        n=n,
    )
    return {"hotspots": hotspots}


async def handle_locate_hotspots(body: dict) -> dict:
    """Find the predicted labels on the finished child image."""
    image_b64 = body.get("image_b64")
    if not image_b64:
        raise HTTPException(status_code=400, detail="image_b64 required")
    located = await _region_picker().locate_hotspots(
        base64.b64decode(image_b64), list(body.get("labels") or [])
    )
    return {"located": located}


async def handle_generate(body: dict, image_generator: ImageGenerator) -> dict:
    """F5: JSON generate — same contract as explainer generate."""
    prompt = body.get("prompt", "")
    local_crop_b64 = body.get("local_crop_b64")
    global_b64 = body.get("global_b64")
    if not local_crop_b64 and settings.MODEL_PROVIDER != "mock":
        raise HTTPException(status_code=400, detail="local_crop_b64 required")
    return await image_generator.generate(prompt, local_crop_b64, global_b64)


async def handle_generate_from_text(body: dict, image_generator: ImageGenerator) -> dict:
    topic = str(body.get("topic", "")).strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic required")
    return await generate_from_text(topic, image_generator=image_generator)
