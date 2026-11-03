"""Waiting file of released tasks (spec §6.4 try_start_waiting).

Ranking rule (POP f9, UM p.41): 1 low priority value first, 2 high first,
3 FIFO (default), 4 LIFO; ties FIFO by release sequence. The whole file is
scanned each time so a blocked head does not block later entries that can start
(ASSUMPTION Q2).
"""

from __future__ import annotations

from ..model.enums import RankingRule
from .tasks import Instance


class WaitingFile:
    def __init__(self, rule: RankingRule = RankingRule.FIFO) -> None:
        self.rule = rule
        self.items: list[Instance] = []

    def insert(self, inst: Instance) -> None:
        self.items.append(inst)

    def remove(self, inst: Instance) -> None:
        self.items.remove(inst)

    def ordered(self) -> list[Instance]:
        r = self.rule
        if r is RankingRule.LOW_VALUE_FIRST:
            return sorted(self.items, key=lambda i: (i.priority, i.seq))
        if r is RankingRule.HIGH_VALUE_FIRST:
            return sorted(self.items, key=lambda i: (-i.priority, i.seq))
        if r is RankingRule.LIFO:
            return sorted(self.items, key=lambda i: -i.seq)
        return sorted(self.items, key=lambda i: i.seq)

    def __len__(self) -> int:
        return len(self.items)
