"""Deterministic F7 auto-drill loop + optional pi-agent prompt mode."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from backend.agent import tools as agent_tools
from backend.app.controllers import tools as layer3
from backend.core.factory import get_service_factory
from backend.shared.image_utils import path_to_b64


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def run_deterministic_drill(
    *,
    parent_id: str | None = None,
    parent_image_b64: str | None = None,
    max_depth: int = 3,
    vision_model: str = "qwen3.5",
    grounding_mode: str = "red_ring",
    session_id: str | None = None,
) -> AsyncIterator[str]:
    """Emit pick events only — client runs confirm drill loop per depth."""
    factory = get_service_factory()
    page_store = factory.create_explainer_page_store()

    if not parent_id:
        if not parent_image_b64:
            yield _sse("error", {"message": "parent_id or parent_image_b64 required"})
            return
        sid = session_id or str(uuid.uuid4())
        agent_tools.register_session(sid, parent_image_b64, max_depth)
        yield _sse("error", {"message": "parent_id required for orchestrated auto-drill"})
        agent_tools.clear_session(sid)
        return

    sid = session_id or str(uuid.uuid4())
    yield _sse("session", {"session_id": sid, "max_depth": max_depth, "parent_id": parent_id})

    current_parent_id = parent_id
    try:
        for depth in range(1, max_depth + 1):
            parent_path = page_store.parent_image_path(current_parent_id)
            if not parent_path.exists():
                raise FileNotFoundError(f"Parent image not found: {parent_path}")

            parent_b64 = path_to_b64(parent_path)
            yield _sse("status", {"depth": depth, "phase": "pick_next_region"})

            pick = await layer3.handle_pick_next_region({"image_b64": parent_b64})
            yield _sse(
                "pick",
                {
                    "depth": depth,
                    "parent_id": current_parent_id,
                    "requires_confirm": True,
                    **pick,
                },
            )
            yield _sse(
                "await_confirm",
                {
                    "depth": depth,
                    "parent_id": current_parent_id,
                    "x": pick["x"],
                    "y": pick["y"],
                    "label": pick.get("label"),
                    "message": "Confirm drill target before continuing auto-drill",
                },
            )
            return

        yield _sse(
            "complete",
            {
                "session_id": sid,
                "final_page_id": current_parent_id,
                "depths": max_depth,
            },
        )
    except Exception as exc:
        yield _sse("error", {"message": str(exc), "session_id": sid})


async def run_pi_agent_drill(
    *,
    topic: str | None,
    parent_image_b64: str | None,
    parent_id: str | None = None,
    max_depth: int = 3,
    vision_model: str = "qwen3.5",
    grounding_mode: str = "red_ring",
) -> AsyncIterator[str]:
    """pi-agent-core drives the tool chain via Reason→Act→Observe loop."""
    from backend.agent.drill_agent import create_drill_agent

    agent, sid = create_drill_agent()
    if parent_image_b64:
        agent_tools.register_session(sid, parent_image_b64, max_depth)
    else:
        agent_tools.register_session(sid, "", max_depth)

    yield _sse("session", {"session_id": sid, "max_depth": max_depth, "mode": "pi-agent"})

    if topic and not parent_image_b64 and not parent_id:
        prompt = (
            f"Session id: {sid}. Start with generate_from_text(topic={topic!r}, session_id={sid!r}), "
            f"then run {max_depth} drill cycles (pick_next_region → analyze → generate) using session_id={sid!r}."
        )
    elif parent_id or parent_image_b64:
        prompt = (
            f"Session id: {sid}. Run {max_depth} drill cycles on the loaded parent image: "
            f"pick_next_region → analyze → generate. Use session_id={sid!r} for every tool call."
        )
    else:
        yield _sse("error", {"message": "topic or parent_id/parent_image_b64 required"})
        agent_tools.clear_session(sid)
        return

    try:
        async with agent:
            yield _sse("status", {"phase": "agent_start"})
            async for event in agent.prompt(prompt):
                etype = event.get("type")
                if etype == "tool_execution_start":
                    yield _sse(
                        "tool_start",
                        {"tool": event.get("toolName"), "params": event.get("params", {})},
                    )
                elif etype == "tool_execution_end":
                    yield _sse("tool_end", {"tool": event.get("toolName")})
                elif etype == "agent_end":
                    yield _sse("agent_end", {})

            chain = agent_tools.get_session_chain(sid)
            final_b64 = chain[-1]["image_b64"] if chain else parent_image_b64
            yield _sse(
                "complete",
                {"session_id": sid, "final_image_b64": final_b64, "chain": chain},
            )
    except Exception as exc:
        yield _sse("error", {"message": str(exc), "session_id": sid})
    finally:
        agent_tools.clear_session(sid)
