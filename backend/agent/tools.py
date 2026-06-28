"""pi-agent ToolDefinitions → Layer 3 tool handlers (same contracts as HTTP)."""

from __future__ import annotations

import json
from typing import Any

from backend.app.controllers import tools as tools_controller
from backend.core.factory import get_service_factory

# Session state keyed by agent run — tools mutate parent_image_b64 in-place
_sessions: dict[str, dict[str, Any]] = {}


def _tool_text(payload: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}


def _session_key(params: dict) -> str:
    return str(params.get("session_id", "default"))


def _get_session(params: dict) -> dict[str, Any]:
    key = _session_key(params)
    if key not in _sessions:
        raise ValueError(f"Unknown session_id: {key}")
    return _sessions[key]


def register_session(session_id: str, parent_image_b64: str, max_depth: int = 3) -> None:
    _sessions[session_id] = {
        "parent_image_b64": parent_image_b64,
        "max_depth": max_depth,
        "depth": 0,
        "chain": [],
    }


def clear_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


def get_session_chain(session_id: str) -> list[dict]:
    sess = _sessions.get(session_id, {})
    return list(sess.get("chain", []))


async def pick_next_region(params: dict) -> dict:
    sess = _get_session(params)
    result = await tools_controller.handle_pick_next_region(
        {"image_b64": sess["parent_image_b64"]}
    )
    sess["last_pick"] = result
    return _tool_text(result)


async def analyze(params: dict) -> dict:
    sess = _get_session(params)
    pick = sess.get("last_pick")
    x = float(params.get("x", pick["x"] if pick else 0.5))
    y = float(params.get("y", pick["y"] if pick else 0.5))
    result = await tools_controller.handle_analyze_b64(
        {"image_b64": sess["parent_image_b64"], "x": x, "y": y, "radius": params.get("radius", 80)}
    )
    sess["last_analyze"] = result
    return _tool_text(result)


async def generate(params: dict) -> dict:
    sess = _get_session(params)
    analyze_result = sess.get("last_analyze")
    if not analyze_result:
        return _tool_text({"error": "Call analyze before generate"})

    body = {
        "prompt": params.get("prompt") or analyze_result.get("image_prompt", ""),
        "local_crop_b64": params.get("local_crop_b64") or analyze_result.get("local_crop_b64"),
        "global_b64": params.get("global_b64") or analyze_result.get("global_b64"),
    }
    image_generator = get_service_factory().create_image_generator()
    result = await tools_controller.handle_generate(body, image_generator)
    child_b64 = result["image_b64"]
    sess["parent_image_b64"] = child_b64
    sess["depth"] = int(sess.get("depth", 0)) + 1
    pick = sess.get("last_pick", {})
    sess["chain"].append(
        {
            "depth": sess["depth"],
            "x": pick.get("x"),
            "y": pick.get("y"),
            "label": pick.get("label"),
            "analysis": analyze_result.get("analysis"),
            "image_prompt": body["prompt"],
            "image_b64": child_b64,
        }
    )
    return _tool_text({"image_b64": child_b64, "depth": sess["depth"]})


async def generate_from_text(params: dict) -> dict:
    topic = str(params.get("topic", "")).strip()
    image_generator = get_service_factory().create_image_generator()
    result = await tools_controller.handle_generate_from_text({"topic": topic}, image_generator)
    session_id = params.get("session_id")
    if session_id and session_id in _sessions:
        _sessions[session_id]["parent_image_b64"] = result["image_b64"]
    return _tool_text(result)


def build_tool_definitions():
    """Lazy import pi_agent to keep Layer 3 usable without SDK installed."""
    from pi_agent import ToolDefinition

    return [
        ToolDefinition(
            name="pick_next_region",
            description=(
                "F7: Use VLM to choose the next drill point on the current parent image. "
                "Requires session_id. Returns normalized x, y, and label."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Active drill session id"},
                },
                "required": ["session_id"],
            },
            execute=pick_next_region,
            execution_mode="sequential",
        ),
        ToolDefinition(
            name="analyze",
            description=(
                "F3+F4: Analyze the clicked region on the parent image via dual-image VLM. "
                "Uses last pick coordinates unless x,y provided. Returns ANALYSIS and IMAGE_PROMPT."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "x": {"type": "number", "description": "Normalized x (optional)"},
                    "y": {"type": "number", "description": "Normalized y (optional)"},
                    "radius": {"type": "integer", "description": "Crop radius in pixels"},
                },
                "required": ["session_id"],
            },
            execute=analyze,
            execution_mode="sequential",
        ),
        ToolDefinition(
            name="generate",
            description=(
                "F5: Generate child image from IMAGE_PROMPT and crops from analyze. "
                "Promotes child to parent in session."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "prompt": {"type": "string"},
                    "local_crop_b64": {"type": "string"},
                    "global_b64": {"type": "string"},
                },
                "required": ["session_id"],
            },
            execute=generate,
            execution_mode="sequential",
        ),
        ToolDefinition(
            name="generate_from_text",
            description="F2 cold start: generate first parent image from a text topic.",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "session_id": {"type": "string"},
                },
                "required": ["topic"],
            },
            execute=generate_from_text,
            execution_mode="sequential",
        ),
    ]
