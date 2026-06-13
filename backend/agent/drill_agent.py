"""pi-agent-core factory for Semantic Drill Down F7."""

from __future__ import annotations

import uuid

from backend.agent.tools import build_tool_definitions
from backend.shared.config import settings

SYSTEM_PROMPT = """You automate Semantic Drill Down (infinite recursive image exploration).

Each drill depth cycle — execute these tools IN ORDER:
  1. pick_next_region(session_id) — VLM chooses where to drill next
  2. analyze(session_id) — dual-image VLM analysis at that point
  3. generate(session_id) — image gen produces the child; it becomes the new parent

Cold start: call generate_from_text(topic, session_id) first to create the parent image.

Stop when you have completed the requested number of depths. Report each depth's label and analysis briefly."""


async def get_ollama_api_key(provider: str) -> str:
    del provider
    return "ollama"


def create_drill_agent(session_id: str | None = None):
    """Return a configured PiAgent context manager for F7 orchestration."""
    from pi_agent import LocalModelConfig, PiAgent, PiAgentOptions

    orchestrator_model = getattr(settings, "AGENT_ORCHESTRATOR_MODEL", "llama3.1")
    model = LocalModelConfig(
        id=orchestrator_model,
        name=orchestrator_model,
        api="openai-completions",
        provider="local",
        base_url=f"{settings.OLLAMA_BASE.rstrip('/')}/v1/",
    )
    tools = build_tool_definitions()
    sid = session_id or str(uuid.uuid4())
    prompt = f"{SYSTEM_PROMPT}\n\nActive session_id for all tool calls: {sid}"
    return PiAgent(
        PiAgentOptions(
            system_prompt=prompt,
            model=model,
            tools=tools,
            get_api_key=get_ollama_api_key,
            tool_execution="sequential",
        )
    ), sid
