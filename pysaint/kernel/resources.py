"""Resources and utilization bookkeeping (spec §4.9, RESR §4.3 item 12).

DESIGN DECISION: OR mode seizes the lowest-numbered idle listed resource.
A task with no resources starts immediately at release.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..model.enums import ResourceMode
from ..model.schema import Model, ResourceReq


@dataclass
class ResourceState:
    rid: int
    attrs: dict[int, float] = field(default_factory=dict)
    busy: bool = False
    busy_since: float = 0.0
    busy_time: float = 0.0
    n_tasks: int = 0


class ResourcePool:
    def __init__(self, model: Model) -> None:
        self.res = {rid: ResourceState(rid, dict(r.attrs)) for rid, r in model.resources.items()}

    def choose(self, req: ResourceReq) -> list[int] | None:
        """Resources that would be seized now, or None if unavailable."""
        if not req.ids:
            return []
        if req.mode is ResourceMode.AND:
            return list(req.ids) if all(not self.res[r].busy for r in req.ids) else None
        for r in sorted(req.ids):
            if not self.res[r].busy:
                return [r]
        return None

    def seize(self, ids: list[int], now: float) -> None:
        for r in ids:
            s = self.res[r]
            s.busy, s.busy_since = True, now
            s.n_tasks += 1

    def release(self, ids: list[int], now: float) -> None:
        for r in ids:
            s = self.res[r]
            s.busy_time += now - s.busy_since
            s.busy = False

    def finalize(self, now: float) -> None:
        """Count busy time of tasks abandoned at iteration end up to ``now``."""
        for s in self.res.values():
            if s.busy:
                s.busy_time += now - s.busy_since
                s.busy_since = now
