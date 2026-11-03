"""Event calendar (spec §6.2).

Key = ``(time, class, -prec, seq)``. Class at equal times: 0 monitor crossing,
1 task completion, 2 continuous save point (only class 1 exists in Step 1).
Higher PREC first (UM p.16); remaining ties FIFO by scheduling sequence
(ASSUMPTION Q3 - the original uses GASP file order).
"""

from __future__ import annotations

import heapq
import itertools
import math
from dataclasses import dataclass, field
from typing import Any

COMPLETION = 1


@dataclass(order=True)
class Event:
    time: float
    cls: int
    neg_prec: float
    seq: int
    payload: Any = field(compare=False)
    cancelled: bool = field(default=False, compare=False)


class Calendar:
    def __init__(self) -> None:
        self._heap: list[Event] = []
        self._seq = itertools.count()

    def schedule(self, time: float, payload: Any, cls: int = COMPLETION,
                 prec: float = 0.0) -> Event:
        ev = Event(time, cls, -prec, next(self._seq), payload)
        heapq.heappush(self._heap, ev)
        return ev

    def _drop_cancelled(self) -> None:
        while self._heap and self._heap[0].cancelled:
            heapq.heappop(self._heap)

    def peek_time(self) -> float:
        self._drop_cancelled()
        return self._heap[0].time if self._heap else math.inf

    def pop(self) -> Event:
        self._drop_cancelled()
        return heapq.heappop(self._heap)

    def __len__(self) -> int:
        self._drop_cancelled()
        return sum(1 for e in self._heap if not e.cancelled)
