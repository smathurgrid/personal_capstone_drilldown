"""Layer 2 agent routes — auto-drill SSE."""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.agent import speculative
from backend.agent.orchestrator import run_deterministic_drill, run_pi_agent_drill
from backend.shared.config import settings
from backend.shared.llm_client import get_llm_client

router = APIRouter(tags=["agent"])


@router.post("/auto-drill")
async def auto_drill(request: Request):
    """
    F7 autonomous drill loop via SSE.

    Body JSON:
      - parent_image_b64: starting image (required unless topic set)
      - topic: cold-start topic (F2)
      - max_depth: drill levels (default 3)
      - mode: "deterministic" (default) | "pi-agent"
    """
    body = await request.json()
    max_depth = int(body.get("max_depth", 3))
    mode = body.get("mode", "deterministic")
    topic = body.get("topic")
    parent_image_b64 = body.get("parent_image_b64")
    parent_id = body.get("parent_id")
    vision_model = body.get("vision_model", "qwen3.5")
    grounding_mode = body.get("grounding_mode", "red_ring")

    if mode == "pi-agent":
        stream = run_pi_agent_drill(
            topic=topic,
            parent_image_b64=parent_image_b64,
            parent_id=parent_id,
            max_depth=max_depth,
            vision_model=vision_model,
            grounding_mode=grounding_mode,
        )
    else:
        if not parent_id and not parent_image_b64:
            return StreamingResponse(
                iter(['event: error\ndata: {"message": "parent_id or parent_image_b64 required"}\n\n']),
                media_type="text/event-stream",
            )
        stream = run_deterministic_drill(
            parent_id=parent_id,
            parent_image_b64=parent_image_b64,
            max_depth=max_depth,
            vision_model=vision_model,
            grounding_mode=grounding_mode,
            session_id=body.get("session_id"),
        )

    return StreamingResponse(stream, media_type="text/event-stream")


@router.post("/spec-drill/start")
async def spec_drill_start(request: Request):
    """Speculative drill: rank top-N hotspots and prefetch their child images (SSE).

    Body JSON:
      - parent_image_b64: starting image (required unless topic set)
      - topic: cold-start topic — generates the first parent image
      - max_depth: drill levels (default 3)
      - hotspots: regions ranked + prefetched per depth (default 5)
      - concurrency: max concurrent image generations (default 2)

    Streams: session, hotspots, prefetch_ready*, depth_ready.
    """
    body = await request.json()
    raw_concurrency = body.get("concurrency")
    stream = speculative.start_session(
        parent_image_b64=body.get("parent_image_b64"),
        topic=body.get("topic"),
        max_depth=int(body.get("max_depth", 3)),
        hotspots=int(body.get("hotspots", speculative.DEFAULT_HOTSPOTS)),
        # None -> engine auto-sizes the fan-out to the worker pool's capacity.
        concurrency=int(raw_concurrency) if raw_concurrency is not None else None,
        # predict=False (uploaded parent) -> no hotspots until the first free click.
        predict=bool(body.get("predict", True)),
    )
    return StreamingResponse(stream, media_type="text/event-stream")


@router.post("/spec-drill/click")
async def spec_drill_click(request: Request):
    """User clicks one of the N hotspots (SSE).

    Body JSON: session_id, hotspot_id.
    Streams: chosen (served from cache instantly), then either complete (at max
    depth) or the next depth's hotspots, prefetch_ready*, depth_ready.
    """
    body = await request.json()
    session_id = body.get("session_id")
    hotspot_id = body.get("hotspot_id")
    if not session_id or not hotspot_id:
        return StreamingResponse(
            iter(['event: error\ndata: {"message": "session_id and hotspot_id required"}\n\n']),
            media_type="text/event-stream",
        )
    return StreamingResponse(
        speculative.click(session_id, hotspot_id), media_type="text/event-stream"
    )


@router.post("/spec-drill/click-point")
async def spec_drill_click_point(request: Request):
    """User clicks an arbitrary point (not a predicted hotspot) — generate that
    child on the fly, then prefetch the next depth's hotspots (SSE).

    Body JSON: session_id, x, y (normalized 0..1).
    Streams: status, chosen, then hotspots, prefetch_ready*, depth_ready (or complete).
    """
    body = await request.json()
    session_id = body.get("session_id")
    x = body.get("x")
    y = body.get("y")
    if not session_id or x is None or y is None:
        return StreamingResponse(
            iter(['event: error\ndata: {"message": "session_id, x and y required"}\n\n']),
            media_type="text/event-stream",
        )
    return StreamingResponse(
        speculative.click_point(session_id, float(x), float(y)),
        media_type="text/event-stream",
    )


@router.post("/spec-drill/back")
async def spec_drill_back(request: Request):
    """Go back to the previous depth and re-offer its hotspots (SSE).

    Body JSON: session_id.
    Streams: back (restored parent image), then hotspots, prefetch_ready*, depth_ready.
    """
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        return StreamingResponse(
            iter(['event: error\ndata: {"message": "session_id required"}\n\n']),
            media_type="text/event-stream",
        )
    return StreamingResponse(
        speculative.go_back(session_id), media_type="text/event-stream"
    )


@router.post("/spec-drill/end")
async def spec_drill_end(request: Request):
    """End a session: cancel in-flight prefetch and flush the tree to SQLite."""
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        return {"error": "session_id required"}
    try:
        return await speculative.end_session(session_id)
    except KeyError as exc:
        return {"error": str(exc)}


@router.get("/health")
async def agent_health():
    try:
        import pi_agent  # noqa: F401

        sdk = "available"
    except ImportError:
        sdk = "missing"
    llm = get_llm_client()
    return {
        "module": "pi-agent",
        "sdk": sdk,
        "llm_provider": settings.LLM_PROVIDER,
        "orchestrator_base_url": llm.openai_compatible_base_url(),
        "tools": ["pick_next_region", "analyze", "generate", "generate_from_text"],
    }
