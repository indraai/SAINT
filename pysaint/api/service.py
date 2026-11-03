"""Framework-free helpers behind the web API: parse, validate, run, graph, CSV."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError
from ruamel.yaml.error import YAMLError

from ..errors import InputReport, SaintError
from ..io import json_io, yaml_io
from ..kernel.engine import Simulation
from ..model.schema import Model
from ..stats.summary import RunResult

Format = Literal["auto", "yaml", "json"]
CSV_TABLES = ("task_summary", "resources", "observations", "iterations", "task_counts")
MAX_ITERATIONS = 100_000


class ParseFailure(Exception):
    """The posted text could not be turned into a Model."""

    def __init__(self, message: str, details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []


def examples_dir() -> Path:
    """Bundled examples: ``$SAINT_EXAMPLES`` or ``<repo>/examples/yaml``."""
    env = os.environ.get("SAINT_EXAMPLES")
    return Path(env) if env else Path(__file__).resolve().parents[2] / "examples" / "yaml"


def list_examples() -> list[dict[str, str]]:
    d = examples_dir()
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("*.y*ml")) + sorted(d.glob("*.json")):
        desc = ""
        for line in p.read_text().splitlines():
            if line.startswith("#"):
                desc = line.lstrip("# ").strip()
                break
        out.append({"name": p.name, "description": desc})
    return out


def read_example(name: str) -> str | None:
    if "/" in name or "\\" in name or name.startswith("."):
        return None
    p = examples_dir() / name
    return p.read_text() if p.is_file() else None


def parse(text: str, fmt: Format = "auto") -> Model:
    if fmt == "auto":
        fmt = "json" if text.lstrip().startswith(("{", "[")) else "yaml"
    try:
        return json_io.loads(text) if fmt == "json" else yaml_io.loads(text)
    except ValidationError as e:
        details = [{"location": ".".join(str(x) for x in err["loc"]), "message": err["msg"]}
                   for err in e.errors()]
        raise ParseFailure(f"model does not match the schema ({len(details)} problem(s))",
                           details) from e
    except (YAMLError, json.JSONDecodeError, ValueError, SaintError) as e:
        raise ParseFailure(f"cannot parse {fmt.upper()}: {e}") from e


def report_dict(rep: InputReport) -> dict[str, Any]:
    def d(x):
        return {"code": x.code, "severity": x.severity, "message": x.message,
                "location": x.location}
    return {"ok": rep.ok, "errors": [d(x) for x in rep.errors],
            "warnings": [d(x) for x in rep.warnings]}


def graph(model: Model) -> dict[str, Any]:
    """Nodes and edges for the network diagram."""
    nodes, edges = [], []
    for tid, t in model.tasks.items():
        nodes.append({"id": tid, "label": t.label or f"T{tid}", "role": t.role.value,
                      "resources": t.resources.ids})
        if t.branching:
            for b in t.branching.targets():
                lab = ""
                if b.p is not None:
                    lab = f"p={b.p:g}"
                elif b.condition is not None:
                    lab = b.condition.code.value
                edges.append({"from": tid, "to": b.to, "type": t.branching.type.value,
                              "label": lab})
    return {"nodes": nodes, "edges": edges}


def run(model: Model, seed: int | None, iterations: int | None) -> RunResult:
    if iterations is not None and not 1 <= iterations <= MAX_ITERATIONS:
        raise ValueError(f"iterations must be between 1 and {MAX_ITERATIONS}")
    return Simulation(model, seed=seed, validate=False).run(iterations)


def result_dict(res: RunResult) -> dict[str, Any]:
    out = res.to_dict()
    out["iterations_table"] = res.iterations_table().to_dict(orient="records")
    return out


def table_csv(res: RunResult, table: str) -> str:
    df = {
        "task_summary": res.task_summary, "resources": res.resource_summary,
        "observations": res.observations, "iterations": res.iterations_table,
        "task_counts": res.task_counts,
    }[table]()
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()
