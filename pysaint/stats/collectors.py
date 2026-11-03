"""Observation collectors (spec §4.4)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Observations:
    """Flat list of observation records; one row per recorded value."""

    rows: list[dict] = field(default_factory=list)

    def add(self, iteration: int, task: int, label: str, stat: str, value: float) -> None:
        self.rows.append({"iteration": iteration, "task": task, "label": label,
                          "stat": stat, "value": float(value)})
