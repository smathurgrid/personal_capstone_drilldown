"""Deterministic F7 auto-drill loop + optional pi-agent prompt mode."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from backend.agent import tools as agent_tools
from backend.app.controllers import tools as layer3
from backend.core.factory import get_service_factory


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def run_deterministic_drill(
    *,
    parent_image_b64: str,
    max_depth: int = 3,
    session_id: str | None = None,
) -> AsyncIterator[str]:
    """F7 loop: pick_next_region → analyze → generate → promote (SSE events)."""
    sid = session_id or str(uuid.uuid4())
    agent_tools.register_session(sid, parent_image_b64, max_depth)
    image_generator = get_service_factory().create_image_generator()

    yield _sse("session", {"session_id": sid, "max_depth": max_depth})

    parent_b64 = parent_image_b64
    try:
        for depth in range(1, max_depth + 1):
            yield _sse("status", {"depth": depth, "phase": "pick_next_region"})

            pick = await layer3.handle_pick_next_region({"image_b64": parent_b64})
            yield _sse("pick", {"depth": depth, **pick})

            yield _sse("status", {"depth": depth, "phase": "analyze", "x": pick["x"], "y": pick["y"]})
            analyze_result = await layer3.handle_analyze_b64(
                {"image_b64": parent_b64, "x": pick["x"], "y": pick["y"], "radius": 80}
            )
            yield _sse(
                "analyze",
                {
                    "depth": depth,
                    "analysis": analyze_result["analysis"],
                    "image_prompt": analyze_result["image_prompt"],
                },
            )

            yield _sse("status", {"depth": depth, "phase": "generate"})
            gen_result = await layer3.handle_generate(
                {
                    "prompt": analyze_result["image_prompt"],
                    "local_crop_b64": analyze_result["local_crop_b64"],
                    "global_b64": analyze_result["global_b64"],
                },
                image_generator,
            )
            parent_b64 = gen_result["image_b64"]
            yield _sse(
                "complete_depth",
                {
                    "depth": depth,
                    "x": pick["x"],
                    "y": pick["y"],
                    "label": pick.get("label"),
                    "image_b64": parent_b64,
                },
            )

        yield _sse("complete", {"session_id": sid, "final_image_b64": parent_b64, "depths": max_depth})
    except Exception as exc:
        yield _sse("error", {"message": str(exc), "session_id": sid})
    finally:
        agent_tools.clear_session(sid)


async def run_pi_agent_drill(
    *,
    topic: str | None,
    parent_image_b64: str | None,
    max_depth: int = 3,
) -> AsyncIterator[str]:
    """pi-agent-core drives the tool chain via Reason→Act→Observe loop."""
    from backend.agent.drill_agent import create_drill_agent

    agent, sid = create_drill_agent()
    if parent_image_b64:
        agent_tools.register_session(sid, parent_image_b64, max_depth)
    else:
        agent_tools.register_session(sid, "", max_depth)

    yield _sse("session", {"session_id": sid, "max_depth": max_depth, "mode": "pi-agent"})

    if topic and not parent_image_b64:
        prompt = (
            f"Session id: {sid}. Start with generate_from_text(topic={topic!r}, session_id={sid!r}), "
            f"then run {max_depth} drill cycles (pick_next_region → analyze → generate) using session_id={sid!r}."
        )
    elif parent_image_b64:
        prompt = (
            f"Session id: {sid}. Run {max_depth} drill cycles on the loaded parent image: "
            f"pick_next_region → analyze → generate. Use session_id={sid!r} for every tool call."
        )
    else:
        yield _sse("error", {"message": "topic or parent_image_b64 required"})
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
