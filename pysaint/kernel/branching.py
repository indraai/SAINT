"""Branch selection on task completion (spec §4.5).

- DET: all branches. PRO: exactly one, by cumulative probability (errors 3003/3004).
- CFI: first satisfied condition in listed order; none satisfied => no successor
  (DESIGN DECISION). CAL: every satisfied branch.
- "Task has been completed" = at least one completion this iteration (ASSUMPTION Q5).
- Attribute-valued probabilities ``(T,A)`` are a later phase.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ..errors import BranchProbabilitySumError, NegativeBranchProbabilityError
from ..model.enums import AttrType, BranchType, CondCode
from ..model.schema import Branch, Branching, Condition
from .tasks import Packet

PROB_TOL = 1e-6


def _attr(c: Condition, which: int | None, packet: Packet, sys_attrs: dict[int, float]) -> float:
    src = packet.attrs if c.attr_type is AttrType.IA else sys_attrs
    return float(src.get(which or 0, 0.0))


def condition_holds(c: Condition, tnow: float, packet: Packet, sys_attrs: dict[int, float],
                    completed: Callable[[int], bool]) -> bool:
    code = c.code
    x = c.value if c.value is not None else 0.0
    if code is CondCode.NO:
        return True
    if code is CondCode.TLV:
        return tnow <= x
    if code is CondCode.TGV:
        return tnow > x
    if code is CondCode.TLA:
        return tnow <= _attr(c, c.attr, packet, sys_attrs)
    if code is CondCode.TGA:
        return tnow > _attr(c, c.attr, packet, sys_attrs)
    if code is CondCode.TVC:
        return completed(int(c.task or 0))
    if code is CondCode.TVN:
        return not completed(int(c.task or 0))
    if code is CondCode.TAC:
        return completed(int(_attr(c, c.attr, packet, sys_attrs)))
    if code is CondCode.TAN:
        return not completed(int(_attr(c, c.attr, packet, sys_attrs)))
    a = _attr(c, c.attr, packet, sys_attrs)
    if code is CondCode.ALV:
        return a <= x
    if code is CondCode.AGV:
        return a > x
    b = _attr(c, c.attr2, packet, sys_attrs)
    if code is CondCode.ALA:
        return a <= b
    if code is CondCode.AGA:
        return a > b
    raise ValueError(code)  # pragma: no cover


def select(b: Branching | None, *, tnow: float, packet: Packet, sys_attrs: dict[int, float],
           completed: Callable[[int], bool], gen: np.random.Generator) -> list[Branch]:
    if b is None:
        return []
    targets = b.targets()
    if b.type is BranchType.DET:
        return targets
    if b.type is BranchType.PRO:
        ps = [br.p if br.p is not None else 0.0 for br in targets]
        if any(p < 0 for p in ps):
            raise NegativeBranchProbabilityError("negative branch probability", tnow=tnow)
        if abs(sum(ps) - 1.0) > PROB_TOL:
            raise BranchProbabilitySumError(f"probabilities sum to {sum(ps)}", tnow=tnow)
        u = float(gen.random())
        acc = 0.0
        for br, p in zip(targets, ps):
            acc += p
            if u < acc:
                return [br]
        return [targets[-1]]
    hits = [br for br in targets if br.condition is not None and
            condition_holds(br.condition, tnow, packet, sys_attrs, completed)]
    return hits[:1] if b.type is BranchType.CFI else hits
