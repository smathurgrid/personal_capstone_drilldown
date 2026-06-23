"""pi-agent-core factory for Semantic Drill Down F7."""

from __future__ import annotations

import uuid

from backend.agent.tools import build_tool_definitions
from backend.shared.config import settings
from backend.shared.llm_client import get_llm_client

SYSTEM_PROMPT = """You automate Semantic Drill Down (infinite recursive image exploration).

Each drill depth cycle — execute these tools IN ORDER:
  1. pick_next_region(session_id) — VLM chooses where to drill next
  2. analyze(session_id) — dual-image VLM analysis at that point
  3. generate(session_id) — image gen produces the child; it becomes the new parent

Cold start: call generate_from_text(topic, session_id) first to create the parent image.

Stop when you have completed the requested number of depths. Report each depth's label and analysis briefly."""


async def get_llm_api_key(provider: str) -> str:
    del provider
    if settings.LLM_PROVIDER == "litellm" and settings.LITELLM_PROXY_BASE:
        return settings.LITELLM_API_KEY or "litellm"
    return "ollama"


def create_drill_agent(session_id: str | None = None):
    """Return a configured PiAgent + session id + trace logger for F7 orchestration."""
    from pi_agent import LocalModelConfig, PiAgent, PiAgentOptions

    from backend.agent.trace_logger import AgentTraceLogger

    llm = get_llm_client()
    orchestrator_model = llm.orchestrator_model_id()
    model = LocalModelConfig(
        id=orchestrator_model,
        name=orchestrator_model,
        api="openai-completions",
        provider="local",
        base_url=llm.openai_compatible_base_url(),
    )
    tools = build_tool_definitions()
    sid = session_id or str(uuid.uuid4())
    prompt = f"{SYSTEM_PROMPT}\n\nActive session_id for all tool calls: {sid}"

    trace = AgentTraceLogger(sid)

    async def before_tool_call(ctx: dict):
        trace.tool_start(ctx.get("id", ""), ctx.get("name", ""), ctx.get("params") or {})
        return None

    async def after_tool_call(ctx: dict):
        trace.tool_end(
            ctx.get("id", ""),
            ctx.get("name", ""),
            ctx.get("result"),
            bool(ctx.get("is_error")),
        )
        return None

    agent = PiAgent(
        PiAgentOptions(
            system_prompt=prompt,
            model=model,
            tools=tools,
            get_api_key=get_llm_api_key,
            tool_execution="sequential",
            before_tool_call=before_tool_call,
            after_tool_call=after_tool_call,
        )
    )
    return agent, sid, trace
