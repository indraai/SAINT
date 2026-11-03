"""Plain-text run report (spec §9.1 items 3-4, Step-1 subset)."""

from __future__ import annotations

import math

from ..stats.summary import RunResult


def _f(x: float) -> str:
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.4g}"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    w = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h)
         for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(w[i]) for i, h in enumerate(headers))
    out = [line, "  ".join("-" * x for x in w)]
    out += ["  ".join(c.ljust(w[i]) for i, c in enumerate(r)) for r in rows]
    return "\n".join(out)


def render(result: RunResult) -> str:
    e = result.end_time()
    parts = [
        f"pySAINT run report: {result.model_name}",
        f"iterations={result.iterations}  seed={result.seed}",
        f"iteration end time: mean={_f(e.mean)} sd={_f(e.sd)} min={_f(e.min)} max={_f(e.max)}",
        "",
        "TASK STATISTICS",
    ]
    ts = result.task_summary()
    parts.append(_table(["task", "label", "stat", "n", "mean", "sd", "min", "max"], [
        [str(r.task), r.label, r.stat, str(r.n), _f(r.mean), _f(r.sd), _f(r.min), _f(r.max)]
        for r in ts.itertuples()]))
    rs = result.resource_summary()
    if len(rs):
        parts += ["", "RESOURCE UTILIZATION (fraction busy)"]
        parts.append(_table(["resource", "label", "mean", "sd", "min", "max", "busy_time",
                             "n_tasks"], [
            [str(r.resource), r.label, _f(r.mean), _f(r.sd), _f(r.min), _f(r.max),
             _f(r.busy_time), _f(r.n_tasks)] for r in rs.itertuples()]))
    if result.warnings:
        parts += ["", "WARNINGS"] + [f"- {w}" for w in result.warnings]
    return "\n".join(parts) + "\n"
