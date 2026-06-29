"""Integration-style tests for v4 drill confirm flow, pending store, and ancestry."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.explainer import pending_drill_store
from backend.services.explainer.page_orchestrator import PageOrchestrator
from backend.shared.errors import AppError


@pytest.fixture
def pending_dir(tmp_path, monkeypatch):
    pending = tmp_path / "pending"
    pending.mkdir()
    static = tmp_path / "static"
    static.mkdir()

    class _Settings:
        EXPLAINER_STATIC_DIR = static

    monkeypatch.setattr(pending_drill_store, "settings", _Settings())
    return pending


def test_pending_drill_persistence_survives_reload(pending_dir):
    pending_drill_store.stash("page-abc", {"page_id": "page-abc", "drill_topic": "test topic"})

    loaded = pending_drill_store.pop("page-abc")
    assert loaded is not None
    assert loaded["drill_topic"] == "test topic"
    assert not (pending_dir / "page-abc.json").exists()


def test_confirm_after_ttl_returns_none(pending_dir, monkeypatch):
    monkeypatch.setattr(pending_drill_store, "DEFAULT_TTL_SECONDS", 1)
    expires = pending_drill_store.stash("expired-page", {"page_id": "expired-page"})
    path = pending_dir / "expired-page.json"
    entry = json.loads(path.read_text())
    entry["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    path.write_text(json.dumps(entry))

    assert pending_drill_store.pop("expired-page") is None
    assert expires  # stash returns ISO timestamp


def test_build_ancestry_chain_uses_object_names(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    repo = MagicMock()
    repo._static_dir = static  # not used directly

    parent_id = "parent123"
    child_id = "child456"
    (static / f"{parent_id}.json").write_text(
        json.dumps(
            {
                "parentId": "root789",
                "depth": 1,
                "metadata": {
                    "object": "Combustor",
                    "drill_mode": "inside",
                    "editorial_headline": "Inside the Combustor Chamber",
                },
            }
        )
    )
    (static / f"{child_id}.json").write_text(
        json.dumps(
            {
                "parentId": parent_id,
                "depth": 2,
                "metadata": {"object": "Fuel Nozzle", "drill_mode": "inside"},
            }
        )
    )
    (static / "root789.json").write_text(
        json.dumps(
            {
                "depth": 0,
                "metadata": {"object": "Turbine Engine", "drill_mode": "inside"},
            }
        )
    )

    orchestrator = PageOrchestrator(
        page_store=MagicMock(),
        grounding_service=MagicMock(),
        drill_context_resolver=MagicMock(),
        image_generator=MagicMock(),
    )
    orchestrator._pages = MagicMock()
    orchestrator._pages.drill_page_paths = lambda pid: (
        static / f"{pid}.png",
        static / f"{pid}.json",
    )

    chain = orchestrator._build_ancestry_chain(child_id)
    assert len(chain) == 3
    assert chain[0] == {"object": "Turbine Engine", "drill_mode": "inside"}
    assert chain[1] == {"object": "Combustor", "drill_mode": "inside"}
    assert chain[2] == {"object": "Fuel Nozzle", "drill_mode": "inside"}


@pytest.mark.asyncio
async def test_confirm_drill_raises_when_session_missing():
    orchestrator = PageOrchestrator(
        page_store=MagicMock(),
        grounding_service=MagicMock(),
        drill_context_resolver=MagicMock(),
        image_generator=MagicMock(),
    )
    with patch(
        "backend.services.explainer.page_orchestrator.pop_pending_drill",
        return_value=None,
    ):
        with pytest.raises(AppError) as exc:
            await orchestrator.confirm_drill("missing-page")
        assert exc.value.code == "DRILL_SESSION_EXPIRED"
        assert exc.value.status_code == 410


@pytest.mark.asyncio
async def test_stream_drill_cache_hit_emits_confirm_not_complete():
    cached_payload = {
        "id": "cached-page",
        "imageUrl": "/static/cached-page.png",
        "context": "Cached drill topic",
        "metadata": {"object": "Valve", "drill_topic": "Cached drill topic"},
    }
    orchestrator = PageOrchestrator(
        page_store=MagicMock(),
        grounding_service=MagicMock(),
        drill_context_resolver=MagicMock(),
        image_generator=MagicMock(),
    )
    orchestrator._drill_preamble = MagicMock(
        return_value={
            "cached": True,
            "payload": cached_payload,
            "page_id": "cached-page",
            "output_path": Path("/tmp/out.png"),
            "metadata_path": Path("/tmp/out.json"),
        }
    )

    events = []
    with patch(
        "backend.services.explainer.page_orchestrator.stash_pending_drill",
        return_value="2099-01-01T00:00:00+00:00",
    ):
        async for event in orchestrator._stream_drill(
            "parent", 0.5, 0.5, "qwen3.5", "red_ring", None
        ):
            events.append(event)

    assert any("confirm" in e for e in events)
    assert not any("complete" in e and "confirm" not in e for e in events)
    confirm_event = next(e for e in events if "confirm" in e)
    assert '"fromCache": true' in confirm_event or '"fromCache":true' in confirm_event


@pytest.mark.asyncio
async def test_get_or_create_page_drill_rejected():
    orchestrator = PageOrchestrator(
        page_store=MagicMock(),
        grounding_service=MagicMock(),
        drill_context_resolver=MagicMock(),
        image_generator=MagicMock(),
    )
    with pytest.raises(AppError) as exc:
        await orchestrator.get_or_create_page(parent_id="p1", x=0.5, y=0.5)
    assert exc.value.code == "DRILL_USE_STREAM"


def test_drill_analyzer_ancestry_prompt_format():
    from backend.shared.config import settings
    from backend.services.explainer.drill_analyzer import DrillAnalyzer

    analyzer = DrillAnalyzer(settings)
    prompt = analyzer._build_prompt(
        parent_context={
            "ancestry_chain": [
                {"object": "Turbine", "drill_mode": "inside"},
                {"object": "Combustor", "drill_mode": "inside"},
            ]
        },
    )
    assert "Drill path: Turbine [inside] → Combustor [inside]" in prompt
