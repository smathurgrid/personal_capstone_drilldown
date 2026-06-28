"""Tests for structured figure parsing."""

from backend.services.knowledge_base.figure_enrichment import (
    _parse_structured_json,
    _structured_to_prose,
)


def test_parse_structured_json_from_fenced_block():
    raw = """```json
    {"figure_type": "schematic", "components": ["SV-204-A"], "purpose": "Relief valve layout"}
    ```"""
    data = _parse_structured_json(raw)
    assert data is not None
    assert data["components"] == ["SV-204-A"]


def test_structured_to_prose_includes_specs():
    prose = _structured_to_prose(
        {
            "purpose": "Shows pump inlet valve",
            "components": ["Relief Valve SV-204-A"],
            "specs": ["45 Nm torque"],
        },
        caption="Fig 4.2",
    )
    assert "SV-204-A" in prose
    assert "45 Nm" in prose
