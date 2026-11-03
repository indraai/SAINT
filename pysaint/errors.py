"""Exception hierarchy and diagnostics (spec §10).

Input diagnostics carry pySAINT codes (I1xx-I5xx, DESIGN DECISION, spec §10.1);
execution errors carry the original SAINT codes (UM Table 14, spec §10.2).
Step 1 implements the subset the core kernel can raise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


class SaintError(Exception):
    """Base class for all pySAINT errors."""

    code: int | str | None = None


# ---------------------------------------------------------------- input side
class SaintInputError(SaintError):
    """Problem found while reading or validating a model."""


class FieldValueError(SaintInputError):
    """I2xx: invalid code, out of range, missing required field."""


class CrossReferenceError(SaintInputError):
    """I4xx: undefined task / distribution / resource / attribute."""


class ConsistencyError(SaintInputError):
    """I5xx: probabilities, branching order, no source/sink, ..."""


Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: Severity
    message: str
    location: str = ""

    def __str__(self) -> str:
        loc = f" [{self.location}]" if self.location else ""
        return f"{self.severity.upper()} {self.code}{loc}: {self.message}"


@dataclass
class InputReport:
    """All diagnostics of a validation pass (collected, not fail-fast)."""

    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == "error"]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_if_errors(self, strict: bool = False) -> None:
        bad = self.diagnostics if strict else self.errors
        if bad:
            raise ModelValidationError(self)


_CLASS_BY_PREFIX: dict[str, type[SaintInputError]] = {
    "I2": FieldValueError, "I4": CrossReferenceError, "I5": ConsistencyError,
}


class ModelValidationError(SaintInputError):
    def __init__(self, report: InputReport) -> None:
        self.report = report
        super().__init__("\n".join(str(d) for d in report.diagnostics))


def exception_class_for(code: str) -> type[SaintInputError]:
    return _CLASS_BY_PREFIX.get(code[:2], SaintInputError)


# ------------------------------------------------------------ execution side
class SaintExecutionError(SaintError):
    """Problem found while a simulation is running (codes 3001-3604)."""

    def __init__(self, message: str, *, tnow: float | None = None,
                 iteration: int | None = None, location: str = "") -> None:
        self.tnow, self.iteration, self.location = tnow, iteration, location
        where = f" (t={tnow}, iteration={iteration})" if tnow is not None else ""
        super().__init__(f"[{self.code}] {message}{where}")


class BranchProbabilitySumError(SaintExecutionError):
    code = 3003


class NegativeBranchProbabilityError(SaintExecutionError):
    code = 3004


class NegativeTaskTimeError(SaintExecutionError):
    code = 3007


class NetworkDeadlockError(SaintExecutionError):
    code = 3010


class DistributionArgumentError(SaintExecutionError):
    code = 3101  # first of the 3101-3127 block; exact sub-code is set per instance


class SimulationLimitExceeded(SaintExecutionError):
    """max_time / max_events safety limit (pySAINT extension, not in SAINT)."""

    code = "X001"
