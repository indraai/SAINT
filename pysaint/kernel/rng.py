"""Random streams and distribution sampling (spec §4.6).

DESIGN DECISIONS
- numpy ``Generator(PCG64)``; per iteration ``SeedSequence(seed, spawn_key=(it,))`` is
  spawned into independent streams (time, branch, assign, user) so any iteration is
  reproducible alone and iterations are order-independent.
- Samples are *clamped* to [min, max] (UM p.45), not drawn from a truncated law.
- NO / LO without an explicit ``min`` default to min=0 so task times are never negative
  (the user brief asked for normal "truncated at 0"; we clamp, as SAINT does).
- Moment-matched parameterisations for LO, BE, GA, BP follow ASSUMPTION Q6.
- EX (exponential) is a pySAINT convenience; SAINT expresses it as ER with k=1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ..errors import DistributionArgumentError
from ..model.enums import DistType
from ..model.schema import Distribution

STREAMS = ("time", "branch", "assign", "user")


@dataclass
class Streams:
    time: np.random.Generator
    branch: np.random.Generator
    assign: np.random.Generator
    user: np.random.Generator


def iteration_streams(seed: int, iteration: int) -> Streams:
    ss = np.random.SeedSequence(seed, spawn_key=(iteration,))
    gens = [np.random.Generator(np.random.PCG64(s)) for s in ss.spawn(len(STREAMS))]
    return Streams(*gens)


def _req(d: Distribution, *names: str) -> list[float]:
    vals = []
    for n in names:
        v = getattr(d, n)
        if v is None:
            raise DistributionArgumentError(f"distribution {d.type.value} needs '{n}'")
        vals.append(float(v))
    return vals


def _beta_on(gen: np.random.Generator, mean: float, sd: float, a: float, b: float) -> float:
    if not b > a or sd <= 0:
        raise DistributionArgumentError("beta needs min < max and sd > 0")
    mu = (mean - a) / (b - a)
    var = (sd / (b - a)) ** 2
    common = mu * (1 - mu) / var - 1
    if not 0 < mu < 1 or common <= 0:
        raise DistributionArgumentError("beta moments infeasible on [min, max]")
    return a + (b - a) * float(gen.beta(mu * common, (1 - mu) * common))


def check(d: Distribution) -> list[str]:
    """Return parameter problems without sampling (used by the validator)."""
    try:
        sample(d, np.random.default_rng(0))
    except DistributionArgumentError as e:
        return [str(e).split("] ", 1)[-1]]
    return []


def sample(d: Distribution, gen: np.random.Generator) -> float:
    t = d.type
    lo = d.min
    hi = d.max
    if t is DistType.CO:
        x = d.value if d.value is not None else (d.mean or 0.0)
        return float(x)
    if t is DistType.NO:
        m, sd = _req(d, "mean", "sd")
        lo = 0.0 if lo is None else lo
        x = float(gen.normal(m, sd)) if sd > 0 else m
    elif t is DistType.LO:
        m, sd = _req(d, "mean", "sd")
        if m <= 0:
            raise DistributionArgumentError("lognormal needs mean > 0")
        s2 = math.log(1 + (sd / m) ** 2)
        x = float(gen.lognormal(math.log(m) - s2 / 2, math.sqrt(s2)))
    elif t is DistType.GA:
        m, sd = _req(d, "mean", "sd")
        if m <= 0 or sd <= 0:
            raise DistributionArgumentError("gamma needs mean > 0, sd > 0")
        x = float(gen.gamma((m / sd) ** 2, sd * sd / m))
    elif t is DistType.BE:
        m, sd, a, b = _req(d, "mean", "sd", "min", "max")
        x = _beta_on(gen, m, sd, a, b)
    elif t is DistType.UN:
        a, b = _req(d, "min", "max")
        if b < a:
            raise DistributionArgumentError("uniform needs min <= max")
        x = float(gen.uniform(a, b))
    elif t in (DistType.ER, DistType.EX):
        (m,) = _req(d, "mean")
        k = d.k if (t is DistType.ER and d.k) else 1
        if m <= 0 or k < 1:
            raise DistributionArgumentError("erlang/exponential needs mean > 0, k >= 1")
        x = float(gen.gamma(k, m))
    elif t is DistType.PO:
        (m,) = _req(d, "mean")
        if m < 0:
            raise DistributionArgumentError("poisson needs mean >= 0")
        x = (lo or 0.0) + float(gen.poisson(m))
    elif t is DistType.TR:
        mo, a, b = _req(d, "mode", "min", "max")
        if not a <= mo <= b or a == b:
            raise DistributionArgumentError("triangular needs min <= mode <= max, min < max")
        x = float(gen.triangular(a, mo, b))
    elif t is DistType.BP:
        mo, a, b = _req(d, "mode", "min", "max")
        if not a <= mo <= b or a == b:
            raise DistributionArgumentError("beta-PERT needs min <= mode <= max, min < max")
        x = _beta_on(gen, (a + 4 * mo + b) / 6, (b - a) / 6, a, b)
    elif t is DistType.WE:
        al, be = _req(d, "alpha", "shape")
        if al <= 0 or be <= 0:
            raise DistributionArgumentError("weibull needs alpha > 0, shape > 0")
        u = 1.0 - float(gen.random())
        x = (-math.log(u) / al) ** (1 / be)
    else:  # pragma: no cover
        raise DistributionArgumentError(f"unknown distribution {t}")
    if lo is not None and x < lo:
        x = lo
    if hi is not None and x > hi:
        x = hi
    return x
