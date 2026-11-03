"""Cross-reference and consistency validation (spec §10.1).

``validate(model) -> InputReport`` collects every diagnostic instead of failing fast.
Codes (DESIGN DECISION, pySAINT catalog):

I201 bad distribution parameters      I401 unknown successor task
I402 unknown resource                 I403 unknown distribution set
I404 duplicate resource in RESR       I405 unknown task in condition
I406 user function without plugin (warning in Step 1)
I501 PRO probabilities do not sum to 1   I502 negative / missing probability
I503 no source task                   I504 no sink task while sinks_to_complete > 0
I505 CFI unconditional branch not last   I506 no sink reachable from a source (warning)
I507 conditional branch without condition  I508 empty branching
"""

from __future__ import annotations

import networkx as nx

from ..errors import Diagnostic, InputReport, Severity
from ..kernel import rng
from .enums import BranchType, CondCode, Role, ValueKind
from .schema import Model, ValueRef

PROB_TOL = 1e-6


def _ref_checks(model: Model, ref: ValueRef, loc: str, add) -> None:
    if ref.kind is ValueKind.DS and int(ref.param) not in model.distributions:
        add("I403", "error", f"unknown distribution set DS {int(ref.param)}", loc)
    if ref.kind is ValueKind.UF:
        add("I406", "warning", f"user function UF {int(ref.param)} must be supplied "
            "via Simulation(userf=...)", loc)
    if ref.kind is ValueKind.DIST and ref.dist is not None:
        for p in rng.check(ref.dist):
            add("I201", "error", p, loc)


def validate(model: Model) -> InputReport:
    report = InputReport()

    def add(code: str, sev: Severity, msg: str, loc: str = "") -> None:
        report.diagnostics.append(Diagnostic(code, sev, msg, loc))

    for n, d in model.distributions.items():
        for p in rng.check(d):
            add("I201", "error", p, f"distributions[{n}]")

    graph = nx.DiGraph()
    graph.add_nodes_from(model.tasks)
    for tid, t in model.tasks.items():
        loc = f"tasks[{tid}]"
        _ref_checks(model, t.time, loc + ".time", add)
        for i, a in enumerate(t.assignments):
            _ref_checks(model, a.value, f"{loc}.assignments[{i}]", add)
        ids = t.resources.ids
        for r in ids:
            if r not in model.resources:
                add("I402", "error", f"unknown resource {r}", loc + ".resources")
        if len(set(ids)) != len(ids):
            add("I404", "error", "duplicate resource id in RESR", loc + ".resources")
        b = t.branching
        if b is None:
            continue
        targets = b.targets()
        if not targets:
            add("I508", "warning", "branching declared with no successors", loc)
        for br in targets:
            if br.to not in model.tasks:
                add("I401", "error", f"unknown successor task {br.to}", loc + ".branching")
            else:
                graph.add_edge(tid, br.to)
        if b.type is BranchType.PRO:
            ps = [br.p for br in targets]
            if any(p is None or p < 0 for p in ps):
                add("I502", "error", "probabilistic branch needs p >= 0 on every branch",
                    loc + ".branching")
            elif abs(sum(p for p in ps if p is not None) - 1.0) > PROB_TOL:
                add("I501", "error", f"probabilities sum to {sum(ps)} (must be 1)",
                    loc + ".branching")
        if b.type in (BranchType.CFI, BranchType.CAL):
            for i, br in enumerate(targets):
                c = br.condition
                if c is None:
                    add("I507", "error", f"branch to {br.to} has no condition", loc)
                    continue
                if c.code is CondCode.NO and b.type is BranchType.CFI and i != len(targets) - 1:
                    add("I505", "error", "unconditional (NO) branch must be last", loc)
                if c.code in (CondCode.TVC, CondCode.TVN) and c.task not in model.tasks:
                    add("I405", "error", f"condition references unknown task {c.task}", loc)

    sources = [tid for tid, t in model.tasks.items() if t.is_source]
    sinks = [tid for tid, t in model.tasks.items() if t.role is Role.SINK]
    if not sources:
        add("I503", "error", "model has no source task (role: source or pr1: 0)")
    if model.general.sinks_to_complete > 0 and not sinks:
        add("I504", "error", "sinks_to_complete > 0 but the model has no sink task")
    if sources and sinks:
        reach = set().union(*(nx.descendants(graph, s) | {s} for s in sources))
        if not reach & set(sinks):
            add("I506", "warning", "no sink is reachable from any source")
    return report
