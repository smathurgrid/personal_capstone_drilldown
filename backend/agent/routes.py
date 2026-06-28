"""Layer 2 agent routes — auto-drill SSE."""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

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
