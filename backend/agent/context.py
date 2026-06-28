"""Shared drill session state for pi-agent F7 loop."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DrillDepthResult:
    depth: int
    x: float
    y: float
    label: str
    analysis: str
    image_prompt: str
    image_b64: str


@dataclass
class DrillSession:
    parent_image_b64: str
    max_depth: int = 3
    depth_results: list[DrillDepthResult] = field(default_factory=list)

    def promote(self, child_b64: str) -> None:
        self.parent_image_b64 = child_b64
