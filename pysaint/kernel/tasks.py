"""Runtime task state and information packets (spec §6.1)."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from ..model.schema import Task

_packet_ids = itertools.count(1)


@dataclass
class Packet:
    """Information packet flowing through the network (IA attributes + mark)."""

    attrs: dict[int, float] = field(default_factory=dict)
    mark: float | None = None
    created: float = 0.0
    pid: int = field(default_factory=lambda: next(_packet_ids))

    def copy(self) -> Packet:
        """Independent copy per branch (ASSUMPTION, spec §6.4)."""
        return Packet(dict(self.attrs), self.mark, self.created)


@dataclass
class Instance:
    """One performance of a task (released -> waiting -> in progress -> done)."""

    task: Task
    packet: Packet
    released_at: float
    seq: int
    priority: float = 0.0
    started_at: float | None = None
    resources: list[int] = field(default_factory=list)


@dataclass
class TaskState:
    task: Task
    req: int
    released_once: bool = False
    diff_seen: set[int] = field(default_factory=set)
    pending: list[Packet] = field(default_factory=list)
    completions: int = 0
    releases: int = 0
    starts: int = 0
    in_progress: int = 0
