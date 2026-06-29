"""Layer 2 agent routes — auto-drill SSE."""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.agent import speculative
from backend.agent.orchestrator import run_deterministic_drill, run_pi_agent_drill
from backend.shared.config import settings
from backend.shared.llm_client import get_llm_client

router = APIRouter(tags=["agent"])


# --- Speculative drill routes (ported optimization, additive) --------------------
@router.post("/spec-drill/start")
async def spec_drill_start(request: Request):
    body = await request.json()
    raw_c = body.get("concurrency")
    stream = speculative.start_session(
        parent_image_b64=body.get("parent_image_b64"),
        topic=body.get("topic"),
        max_depth=int(body.get("max_depth", 3)),
        hotspots=int(body.get("hotspots", speculative.DEFAULT_HOTSPOTS)),
        concurrency=int(raw_c) if raw_c is not None else None,
        predict=bool(body.get("predict", True)),
    )
    return StreamingResponse(stream, media_type="text/event-stream")


@router.post("/spec-drill/click")
async def spec_drill_click(request: Request):
    body = await request.json()
    sid, hid = body.get("session_id"), body.get("hotspot_id")
    if not sid or not hid:
        return StreamingResponse(
            iter(['event: error\ndata: {"message": "session_id and hotspot_id required"}\n\n']),
            media_type="text/event-stream",
        )
    return StreamingResponse(speculative.click(sid, hid), media_type="text/event-stream")


@router.post("/spec-drill/click-point")
async def spec_drill_click_point(request: Request):
    body = await request.json()
    sid, x, y = body.get("session_id"), body.get("x"), body.get("y")
    if not sid or x is None or y is None:
        return StreamingResponse(
            iter(['event: error\ndata: {"message": "session_id, x and y required"}\n\n']),
            media_type="text/event-stream",
        )
    return StreamingResponse(
        speculative.click_point(sid, float(x), float(y)), media_type="text/event-stream"
    )


@router.post("/spec-drill/back")
async def spec_drill_back(request: Request):
    body = await request.json()
    sid = body.get("session_id")
    if not sid:
        return StreamingResponse(
            iter(['event: error\ndata: {"message": "session_id required"}\n\n']),
            media_type="text/event-stream",
        )
    return StreamingResponse(speculative.go_back(sid), media_type="text/event-stream")


@router.post("/spec-drill/end")
async def spec_drill_end(request: Request):
    body = await request.json()
    sid = body.get("session_id")
    if not sid:
        return {"error": "session_id required"}
    try:
        return await speculative.end_session(sid)
    except KeyError as exc:
        return {"error": str(exc)}


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
