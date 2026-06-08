from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class SceneSampleResult:
    updated_count: int = 0
    skipped: list[str] = field(default_factory=list)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)


def apply_cycles_samples(
    scenes: Sequence[object],
    *,
    render_samples: int,
    viewport_samples: int,
    adaptive_threshold: float,
) -> SceneSampleResult:
    if render_samples < 1:
        raise ValueError("Render samples must be greater than zero.")
    if viewport_samples < 1:
        raise ValueError("Viewport samples must be greater than zero.")
    if adaptive_threshold <= 0:
        raise ValueError("Adaptive threshold must be greater than zero.")

    result = SceneSampleResult()

    for scene in scenes:
        engine = getattr(scene.render, "engine", "")
        if engine != "CYCLES":
            result.skipped.append(f"{scene.name}: render engine is {engine}")
            continue

        cycles = getattr(scene, "cycles", None)
        if cycles is None:
            result.skipped.append(f"{scene.name}: missing cycles settings")
            continue

        cycles.samples = render_samples
        if hasattr(cycles, "preview_samples"):
            cycles.preview_samples = viewport_samples
        if hasattr(cycles, "adaptive_threshold"):
            cycles.adaptive_threshold = adaptive_threshold

        result.updated_count += 1

    return result
