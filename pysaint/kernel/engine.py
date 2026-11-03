"""Simulation class and the discrete-event loop (spec §6).

Public API (stable)::

    sim = Simulation(model, seed=None, userf=None, validate=True)
    result: RunResult = sim.run(iterations=None)

Step-1 scope: source release at t=0, predecessor-count release (PR1 first, then
PR2; DIFF), INCM packet choice, waiting file with ranking rules, resource
seizure (AND/OR), sampled task times, MARK/ATAS/STAT at FPC/REL/STA/COM,
DET/PRO/CFI/CAL branching, sink termination, per-iteration seed streams,
resource utilization and task statistics. Not yet: moderators, clearing,
network/distribution modification, switches, regulations, continuous state.

DESIGN DECISIONS (documented per spec §6):
- Each iteration fully re-initializes all state (ASSUMPTION Q8).
- Tasks still in progress when the sink count is reached are abandoned; their
  resource busy time up to the end is still counted toward utilization.
- Utilization = busy_time / iteration end time (end time = TNOW of the event that
  terminated the iteration). OR-resources count only the seized resource.
- Calendar empty before enough sinks complete => ``NetworkDeadlockError`` (3010).
  If at least one sink completed and ``sinks_to_complete`` is 0 the run just ends.
- ``general.max_time``: events after it are not processed; the iteration ends at
  max_time (not an error, logged in ``RunResult.warnings`` once).
- Built-in stats ``completion_time``, ``duration`` and ``interval`` are collected for
  every task in addition to user STAT specs.
- SC constants are divided by ``general.scale`` (GEN f10).
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable
from typing import Any

from ..errors import NegativeTaskTimeError, NetworkDeadlockError, SimulationLimitExceeded
from ..model.enums import AttrType, IncomingRule, Role, Timing, ValueKind
from ..model.schema import Model, Task, ValueRef
from ..model.validate import validate as validate_model
from ..stats.collectors import Observations
from ..stats.summary import RunResult
from ..stats.task_stats import StatCollector
from . import branching, rng
from .events import Calendar
from .queue import WaitingFile
from .resources import ResourcePool
from .tasks import Instance, Packet, TaskState

UserFunction = Callable[["Context", int], float]


class Context:
    """What user functions see (subset of the spec §8.2 support API)."""

    def __init__(self, sim: _Iteration) -> None:
        self._it = sim

    @property
    def TNOW(self) -> float:
        return self._it.tnow

    @property
    def SA(self) -> dict[int, float]:
        return self._it.sys_attrs

    @property
    def rng(self) -> Any:
        return self._it.streams.user

    @property
    def iteration(self) -> int:
        return self._it.number


class _Iteration:
    """State and procedures of one iteration (spec §6.3-6.4)."""

    def __init__(self, sim: Simulation, number: int, obs: Observations) -> None:
        m = sim.model
        self.sim, self.model, self.number, self.obs = sim, m, number, obs
        self.streams = rng.iteration_streams(sim.seed, number)
        self.tnow = 0.0
        self.calendar = Calendar()
        self.waiting = WaitingFile(m.options.ranking)
        self.pool = ResourcePool(m)
        self.sys_attrs = dict(m.system_attrs)
        self.states = {tid: TaskState(t, t.first_release_count) for tid, t in m.tasks.items()}
        self.collectors = {tid: [StatCollector(tid, t.label, s) for s in t.stat]
                           for tid, t in m.tasks.items()}
        self.last_completion: dict[int, float] = {}
        self.sinks_done = 0
        self.events = 0
        self.seq = itertools.count()
        self.ctx = Context(self)

    # -------------------------------------------------------------- helpers
    def value(self, ref: ValueRef, packet: Packet) -> float:
        k = ref.kind
        if k is ValueKind.SC:
            return ref.param / self.model.general.scale
        if k is ValueKind.DS:
            return rng.sample(self.model.distributions[int(ref.param)], self.streams.time)
        if k is ValueKind.DIST:
            assert ref.dist is not None
            return rng.sample(ref.dist, self.streams.time)
        if k is ValueKind.IA:
            return packet.attrs.get(int(ref.param), 0.0)
        if k is ValueKind.SA:
            return self.sys_attrs.get(int(ref.param), 0.0)
        fn = self.sim.userf.get(int(ref.param))
        if fn is None:
            raise KeyError(f"user function UF {int(ref.param)} not supplied")
        return float(fn(self.ctx, int(ref.param)))

    def point(self, task: Task, at: Timing, packet: Packet) -> None:
        """Apply MARK, ATAS and STAT for an event point (order: MARK, ATAS, STAT)."""
        if task.mark is not None and task.mark.at is at:
            packet.mark = self.tnow
        for a in task.assignments:
            if a.at is at:
                v = self.value(a.value, packet)
                (packet.attrs if a.target is AttrType.IA else self.sys_attrs)[a.index] = v
        mark = packet.mark if packet.mark is not None else packet.created
        for c in self.collectors[task.id]:
            c.on_event(at, self.tnow, mark, self.number, self.obs)

    # ----------------------------------------------------------- procedures
    def predecessor_completed(self, tid: int, pred: int | None, packet: Packet) -> None:
        s = self.states[tid]
        t = s.task
        if t.diff and pred is not None:
            if pred in s.diff_seen:
                return
            s.diff_seen.add(pred)
        if not s.pending:
            self.point(t, Timing.FPC, packet)
        s.pending.append(packet)
        s.req -= 1
        if s.req <= 0:
            self.release(s)

    def choose_packet(self, s: TaskState) -> Packet:
        t, pk = s.task, s.pending
        if not pk:
            return Packet(created=self.tnow)
        if t.incm is IncomingRule.FIRST:
            return pk[0]
        if t.incm in (IncomingRule.BIG, IncomingRule.SMALL):
            a = t.incm_attr or 1
            sign = 1 if t.incm is IncomingRule.BIG else -1
            best = pk[0]
            for p in pk[1:]:  # ties keep the earlier packet
                if sign * p.attrs.get(a, 0.0) > sign * best.attrs.get(a, 0.0):
                    best = p
            return best
        return pk[-1]

    def release(self, s: TaskState) -> None:
        packet = self.choose_packet(s)
        s.pending.clear()
        s.diff_seen.clear()
        s.req = s.task.pr2
        s.released_once = True
        s.releases += 1
        self.point(s.task, Timing.REL, packet)
        self.waiting.insert(Instance(s.task, packet, self.tnow, next(self.seq),
                                     priority=s.task.priority))

    def try_start_waiting(self) -> None:
        for inst in self.waiting.ordered():
            ids = self.pool.choose(inst.task.resources)
            if ids is None:
                continue
            self.waiting.remove(inst)
            self.pool.seize(ids, self.tnow)
            inst.resources = ids
            self.start(inst)

    def start(self, inst: Instance) -> None:
        t = inst.task
        s = self.states[t.id]
        s.starts += 1
        s.in_progress += 1
        inst.started_at = self.tnow
        self.point(t, Timing.STA, inst.packet)
        ttime = self.value(t.time, inst.packet)
        if ttime < 0:
            raise NegativeTaskTimeError(f"task {t.id} time {ttime} < 0",
                                        tnow=self.tnow, iteration=self.number)
        self.calendar.schedule(self.tnow + ttime, inst, prec=t.prec)

    def complete(self, inst: Instance) -> None:
        t = inst.task
        s = self.states[t.id]
        self.pool.release(inst.resources, self.tnow)
        s.in_progress -= 1
        s.completions += 1
        self.point(t, Timing.COM, inst.packet)
        o, lab = self.obs, t.label
        o.add(self.number, t.id, lab, "completion_time", self.tnow)
        o.add(self.number, t.id, lab, "duration", self.tnow - (inst.started_at or 0.0))
        if t.id in self.last_completion:
            o.add(self.number, t.id, lab, "interval", self.tnow - self.last_completion[t.id])
        self.last_completion[t.id] = self.tnow
        if t.role is Role.SINK:
            self.sinks_done += 1
        chosen = branching.select(
            t.branching, tnow=self.tnow, packet=inst.packet, sys_attrs=self.sys_attrs,
            completed=lambda n: n in self.states and self.states[n].completions > 0,
            gen=self.streams.branch)
        for br in chosen:
            self.predecessor_completed(br.to, t.id, inst.packet.copy())

    # ----------------------------------------------------------------- loop
    def run(self) -> None:
        g = self.model.general
        need = g.sinks_to_complete
        for s in self.states.values():
            if s.task.is_source and s.req <= 0:
                self.release(s)
        self.try_start_waiting()
        while True:
            if need and self.sinks_done >= need:
                break
            t_next = self.calendar.peek_time()
            if t_next == math.inf:
                if need and self.sinks_done < need:
                    raise NetworkDeadlockError(
                        f"{self.sinks_done}/{need} sinks completed and no task in progress",
                        tnow=self.tnow, iteration=self.number)
                break
            if t_next > g.max_time:
                self.tnow = g.max_time
                self.sim._note(f"iterations stopped at max_time={g.max_time}")
                break
            self.events += 1
            if self.events > g.max_events:
                raise SimulationLimitExceeded(f"more than {g.max_events} events",
                                              tnow=self.tnow, iteration=self.number)
            ev = self.calendar.pop()
            self.tnow = ev.time
            self.complete(ev.payload)
            self.try_start_waiting()
        self.finish()

    def finish(self) -> None:
        r = self.sim.result
        end = self.tnow
        self.pool.finalize(end)
        for cs in self.collectors.values():
            for c in cs:
                c.end_iteration(self.number, self.obs)
        for tid, s in self.states.items():
            r.count_rows.append({"iteration": self.number, "task": tid, "label": s.task.label,
                                 "releases": s.releases, "starts": s.starts,
                                 "completions": s.completions})
        for rid, rs in self.pool.res.items():
            r.resource_rows.append({
                "iteration": self.number, "resource": rid,
                "label": self.model.resources[rid].label, "busy_time": rs.busy_time,
                "utilization": rs.busy_time / end if end > 0 else 0.0,
                "n_tasks": rs.n_tasks})
        r.iteration_rows.append({"iteration": self.number, "end_time": end,
                                 "events": self.events, "sinks_done": self.sinks_done})


class Simulation:
    """Run a model for ``iterations`` independent replications.

    ``seed`` defaults to ``model.general.seed``; iteration *i* (1-based) always uses
    ``SeedSequence(seed, spawn_key=(i,))`` so results are reproducible and independent
    of how many iterations are run. ``userf`` maps UF numbers to ``fn(ctx, n) -> float``.
    """

    def __init__(self, model: Model, seed: int | None = None,
                 userf: dict[int, UserFunction] | None = None, validate: bool = True) -> None:
        self.model = model
        self.seed = model.general.seed if seed is None else seed
        self.userf = dict(userf or {})
        if validate:
            validate_model(model).raise_if_errors()
        self.result = RunResult(model.general.name, self.seed, 0)

    def _note(self, msg: str) -> None:
        if msg not in self.result.warnings:
            self.result.warnings.append(msg)

    def run(self, iterations: int | None = None) -> RunResult:
        n = iterations or self.model.general.iterations
        self.result = RunResult(self.model.general.name, self.seed, n)
        obs = Observations(self.result.obs_rows)
        for i in range(1, n + 1):
            _Iteration(self, i, obs).run()
        return self.result


def run(model: Model, **kw: Any) -> RunResult:
    iterations = kw.pop("iterations", None)
    return Simulation(model, **kw).run(iterations)
