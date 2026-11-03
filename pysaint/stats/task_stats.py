"""Statistics-task data collection: FIR/ALL/BET/INT/NUM x REL/STA/COM/CLR (spec §4.4).

Definitions (DESIGN DECISION following GASP/P-GERT conventions, ASSUMPTION Q1):
FIR = TNOW of first occurrence; ALL = TNOW of every occurrence; BET = time since
previous occurrence (first only sets the reference); INT = TNOW - packet mark
(packets never marked use their creation time); NUM = count, recorded at iteration end.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..model.enums import StatType, Timing
from ..model.schema import StatSpec
from .collectors import Observations


@dataclass
class StatCollector:
    task: int
    label: str
    spec: StatSpec
    last: float | None = None
    count: int = 0

    @property
    def name(self) -> str:
        return f"{self.spec.type.value}-{self.spec.at.value}"

    def reset(self) -> None:
        self.last, self.count = None, 0

    def on_event(self, at: Timing, tnow: float, mark: float, it: int, obs: Observations) -> None:
        if at is not self.spec.at:
            return
        t = self.spec.type
        self.count += 1
        if t is StatType.FIR and self.count == 1 or t is StatType.ALL:
            obs.add(it, self.task, self.label, self.name, tnow)
        elif t is StatType.BET:
            if self.last is not None:
                obs.add(it, self.task, self.label, self.name, tnow - self.last)
            self.last = tnow
        elif t is StatType.INT:
            obs.add(it, self.task, self.label, self.name, tnow - mark)

    def end_iteration(self, it: int, obs: Observations) -> None:
        if self.spec.type is StatType.NUM:
            obs.add(it, self.task, self.label, self.name, self.count)
