"""CSV export via pandas (spec §9.2; parquet comes later).

``export_csv(result, path)``: if ``path`` ends with ``.csv`` the task summary is
written there and sibling files ``<stem>_resources.csv``, ``<stem>_observations.csv``,
``<stem>_iterations.csv`` alongside; otherwise ``path`` is a directory receiving
``task_summary.csv``, ``resources.csv``, ``observations.csv``, ``iterations.csv``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..stats.summary import RunResult


def export_csv(result: RunResult, path: str | Path) -> list[str]:
    p = Path(path)
    tables = {
        "task_summary": result.task_summary(),
        "resources": result.resource_summary(),
        "observations": result.observations(),
        "iterations": result.iterations_table(),
    }
    if p.suffix.lower() == ".csv":
        p.parent.mkdir(parents=True, exist_ok=True)
        targets = {k: p if k == "task_summary" else p.with_name(f"{p.stem}_{k}.csv")
                   for k in tables}
    else:
        p.mkdir(parents=True, exist_ok=True)
        targets = {k: p / f"{k}.csv" for k in tables}
    for k, df in tables.items():
        df.to_csv(targets[k], index=False)
    return [str(v) for v in targets.values()]
