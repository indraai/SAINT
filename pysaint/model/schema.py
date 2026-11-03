"""Pydantic v2 models for a pySAINT model (spec §4, §5.4).

Step-1 subset: tasks, resources, distributions, system attributes, run
settings. Continuous state, monitors, moderators and clearing are later phases;
the field names follow the spec so they can be added without breaking files.

YAML shape (see ``examples/yaml``)::

    saint: "1.0"
    general: {name: X, iterations: 100, sinks_to_complete: 1, seed: 71268659}
    options: {ranking: FIFO}
    distributions: {3: {type: NO, mean: 5.75, sd: 1.2, min: 2, max: 12}}
    resources: {1: {label: OPERATOR}}
    system_attrs: {1: 0.0}
    tasks:
      1: {label: START, role: source, time: {SC: 1}, branching: {type: DET, successors: [2]}}

Mapping keys are ids; an ``id`` inside the value is filled from the key.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from .enums import (
    AttrType,
    BranchType,
    CondCode,
    DistType,
    IncomingRule,
    RankingRule,
    ResourceMode,
    Role,
    StatType,
    Timing,
    ValueKind,
)


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Distribution(_Base):
    """A distribution set (DIS card). Unused fields are ignored per type.

    Parameters by type: CO value; NO/LO/GA/BE mean, sd; UN min,max; ER mean (of each
    exponential), k; EX mean; PO mean (added to min); TR/BP mode, min (a), max (b);
    WE alpha, shape. ``min``/``max`` clamp samples (UM p.45: clamping, not truncation).
    """

    type: DistType = DistType.CO
    value: float | None = None
    mean: float | None = None
    sd: float | None = None
    min: float | None = Field(default=None, alias="low")
    max: float | None = Field(default=None, alias="high")
    mode: float | None = None
    k: int | None = None
    alpha: float | None = None
    shape: float | None = None


class ValueRef(_Base):
    """(function type, parameter) reference, e.g. ``{DS: 3}``, ``{SC: 2.5}``.

    Shorthands accepted: a bare number (= SC), ``{DS: n}``, ``{SC: x}``, ``{UF: n}``,
    ``{IA: a}``, ``{SA: a}``, ``{dist: {...}}`` (inline distribution).
    """

    kind: ValueKind = ValueKind.SC
    param: float = 0.0
    dist: Distribution | None = None

    @model_validator(mode="before")
    @classmethod
    def _shorthand(cls, v: Any) -> Any:
        if isinstance(v, (int, float)):
            return {"kind": "SC", "param": v}
        if isinstance(v, dict) and "kind" not in v and len(v) == 1:
            (key, val), = v.items()
            key = str(key).upper()
            if key == "DIST":
                return {"kind": "DIST", "dist": val}
            return {"kind": key, "param": val}
        return v

    @model_serializer
    def _ser(self) -> Any:
        if self.kind is ValueKind.DIST:
            assert self.dist is not None
            return {"dist": self.dist.model_dump(mode="json", exclude_none=True)}
        p = self.param
        return {self.kind.value: int(p) if self.kind is not ValueKind.SC and p == int(p) else p}


class ResourceReq(_Base):
    mode: ResourceMode = ResourceMode.AND
    ids: list[int] = Field(default_factory=list)


class Condition(_Base):
    """Conditional-branch test. ``value`` = x; ``attr``/``attr2`` = A/B; ``task`` = N."""

    code: CondCode = CondCode.NO
    value: float | None = None
    attr: int | None = None
    attr2: int | None = None
    attr_type: AttrType = AttrType.IA
    task: int | None = None


class Branch(_Base):
    to: int
    p: float | None = None
    condition: Condition | None = None


class Branching(_Base):
    """Output side. ``successors`` is a DET shorthand for ``branches: [{to: n}, ...]``."""

    type: BranchType = BranchType.DET
    successors: list[int] = Field(default_factory=list)
    branches: list[Branch] = Field(default_factory=list)

    def targets(self) -> list[Branch]:
        return self.branches + [Branch(to=s) for s in self.successors]


class Histogram(_Base):
    cells: int = 25
    first: float = 0.0
    width: float = 1.0


class StatSpec(_Base):
    """STAT: statistic type collected at an event point (spec §4.4)."""

    type: StatType = StatType.ALL
    at: Timing = Timing.COM
    hist: Histogram | None = None


class MarkSpec(_Base):
    at: Timing = Timing.COM


class Assignment(_Base):
    """ATAS: ``target`` IA/SA attribute ``index`` <- ``value`` at ``at``."""

    at: Timing = Timing.REL
    target: AttrType = AttrType.IA
    index: int
    value: ValueRef


class Task(_Base):
    id: int = Field(ge=1)
    label: str = ""
    role: Role = Role.NS
    pr1: int | None = None  # default: 0 for source, else 1
    pr2: int = 9999
    time: ValueRef = Field(default_factory=ValueRef)
    priority: float = 0.0
    diff: bool = False
    incm: IncomingRule = IncomingRule.LAST
    incm_attr: int | None = None
    prec: float = 0.0
    resources: ResourceReq = Field(default_factory=ResourceReq)
    branching: Branching | None = None
    stat: list[StatSpec] = Field(default_factory=list)
    mark: MarkSpec | None = None
    assignments: list[Assignment] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _norm(cls, v: Any) -> Any:
        if isinstance(v, dict) and isinstance(v.get("stat"), dict):
            v = {**v, "stat": [v["stat"]]}
        return v

    @property
    def first_release_count(self) -> int:
        if self.pr1 is not None:
            return self.pr1
        return 0 if self.role is Role.SOURCE else 1

    @property
    def is_source(self) -> bool:
        return self.role is Role.SOURCE or self.first_release_count == 0


class Resource(_Base):
    id: int = Field(ge=1)
    label: str = ""
    attrs: dict[int, float] = Field(default_factory=dict)


class General(_Base):
    name: str = "MODEL"
    iterations: int = Field(default=1, ge=1)
    sinks_to_complete: int = Field(default=1, ge=0)
    seed: int = 71268659
    scale: float = 1.0
    max_time: float = math.inf  # pySAINT safety limit (not in SAINT)
    max_events: int = 10_000_000


class Options(_Base):
    ranking: RankingRule = RankingRule.FIFO


def _inject_ids(d: Any) -> Any:
    if isinstance(d, list):
        d = {item["id"]: item for item in d}
    if isinstance(d, dict):
        out = {}
        for k, v in d.items():
            if isinstance(v, dict) and "id" not in v:
                v = {**v, "id": int(k)}
            out[int(k)] = v
        return out
    return d


class Model(_Base):
    saint: str = "1.0"
    general: General = Field(default_factory=General)
    options: Options = Field(default_factory=Options)
    distributions: dict[int, Distribution] = Field(default_factory=dict)
    resources: dict[int, Resource] = Field(default_factory=dict)
    system_attrs: dict[int, float] = Field(default_factory=dict)
    tasks: dict[int, Task] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _ids(cls, v: Any) -> Any:
        if isinstance(v, dict):
            v = dict(v)
            for key in ("tasks", "resources"):
                if key in v:
                    v[key] = _inject_ids(v[key])
        return v

    @model_validator(mode="after")
    def _keys_match(self) -> Model:
        for key, coll in (("tasks", self.tasks), ("resources", self.resources)):
            for k, item in coll.items():
                if item.id != k:
                    raise ValueError(f"{key}[{k}] has mismatched id {item.id}")
        return self
