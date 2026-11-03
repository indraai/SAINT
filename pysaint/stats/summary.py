"""Run results and multi-iteration summaries (spec §9.3).

``RunResult`` is the stable output of ``Simulation(model).run()``; the web API and
reports build on it. Tables (pandas DataFrames, stable column names):

- ``observations()``: iteration, task, label, stat, value. Built-in stats for every
  task: ``completion_time`` (TNOW at each completion), ``duration`` (start->complete),
  ``interval`` (time between successive completions). STAT specs add e.g. ``INT-COM``.
- ``task_summary()``: task, label, stat, n, mean, sd, min, max, ci95.
- ``task_counts()``: iteration, task, label, releases, starts, completions.
- ``resources()``: iteration, resource, label, busy_time, utilization, n_tasks.
- ``resource_summary()``: resource, label, mean/sd/min/max utilization, busy_time, n_tasks.
- ``iterations_table()``: iteration, end_time, events, sinks_done.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Summary:
    n: int
    mean: float
    sd: float
    min: float
    max: float

    @property
    def ci95(self) -> float:
        """Half-width of a normal-approximation 95% CI of the mean."""
        return 1.96 * self.sd / math.sqrt(self.n) if self.n > 1 else math.nan

    @classmethod
    def of(cls, values: Any) -> Summary:
        a = np.asarray(list(values), dtype=float)
        if a.size == 0:
            return cls(0, math.nan, math.nan, math.nan, math.nan)
        sd = float(a.std(ddof=1)) if a.size > 1 else 0.0
        return cls(int(a.size), float(a.mean()), sd, float(a.min()), float(a.max()))


def _summ(df: pd.DataFrame, keys: list[str], col: str) -> pd.DataFrame:
    rows = []
    for k, g in df.groupby(keys, sort=True):
        s = Summary.of(g[col])
        k = k if isinstance(k, tuple) else (k,)
        rows.append({**dict(zip(keys, k)), "n": s.n, "mean": s.mean, "sd": s.sd,
                     "min": s.min, "max": s.max, "ci95": s.ci95})
    cols = keys + ["n", "mean", "sd", "min", "max", "ci95"]
    return pd.DataFrame(rows, columns=cols)


@dataclass
class RunResult:
    model_name: str
    seed: int
    iterations: int
    obs_rows: list[dict] = field(default_factory=list)
    count_rows: list[dict] = field(default_factory=list)
    resource_rows: list[dict] = field(default_factory=list)
    iteration_rows: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # --- tables
    def observations(self) -> pd.DataFrame:
        return pd.DataFrame(self.obs_rows, columns=["iteration", "task", "label", "stat", "value"])

    def task_counts(self) -> pd.DataFrame:
        return pd.DataFrame(self.count_rows, columns=[
            "iteration", "task", "label", "releases", "starts", "completions"])

    def resources(self) -> pd.DataFrame:
        return pd.DataFrame(self.resource_rows, columns=[
            "iteration", "resource", "label", "busy_time", "utilization", "n_tasks"])

    def iterations_table(self) -> pd.DataFrame:
        return pd.DataFrame(self.iteration_rows, columns=[
            "iteration", "end_time", "events", "sinks_done"])

    # --- summaries
    def task_summary(self) -> pd.DataFrame:
        return _summ(self.observations(), ["task", "label", "stat"], "value")

    def resource_summary(self) -> pd.DataFrame:
        df = self.resources()
        out = _summ(df, ["resource", "label"], "utilization")
        if len(df):
            agg = df.groupby("resource").agg(busy_time=("busy_time", "mean"),
                                             n_tasks=("n_tasks", "mean")).reset_index()
            out = out.merge(agg, on="resource")
        return out

    def end_time(self) -> Summary:
        return Summary.of(r["end_time"] for r in self.iteration_rows)

    def stat(self, task: int, stat: str) -> Summary:
        """Summary of one statistic across all iterations, e.g. ``stat(5, "INT-COM")``."""
        return Summary.of(r["value"] for r in self.obs_rows
                          if r["task"] == task and r["stat"] == stat)

    def utilization(self, resource: int) -> Summary:
        return Summary.of(r["utilization"] for r in self.resource_rows
                          if r["resource"] == resource)

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly payload for the upcoming web API."""
        def recs(df: pd.DataFrame) -> list[dict]:
            return df.replace({np.nan: None}).to_dict(orient="records")
        return {
            "model": self.model_name, "seed": self.seed, "iterations": self.iterations,
            "end_time": vars(self.end_time()) if self.iteration_rows else None,
            "tasks": recs(self.task_summary()), "resources": recs(self.resource_summary()),
            "warnings": list(self.warnings),
        }

    def export_csv(self, path: str) -> list[str]:
        from ..report.export import export_csv
        return export_csv(self, path)
