"""Enumerations for the pySAINT model schema (spec §4).

Values match the legacy card codes so the future card parser can map 1:1.
"""

from __future__ import annotations

from enum import Enum, IntEnum


class Role(str, Enum):
    """Task role (TAS f10): normal, source (released at t=0) or sink."""

    NS = "NS"
    SOURCE = "SO"
    SINK = "SI"

    @classmethod
    def _missing_(cls, value: object) -> Role | None:
        aliases = {"normal": cls.NS, "source": cls.SOURCE, "sink": cls.SINK}
        return aliases.get(str(value).lower())


class ResourceMode(str, Enum):
    """RESR combination: AND = all listed, OR = any one listed."""

    AND = "AND"
    OR = "OR"


class BranchType(str, Enum):
    """Output-side branching (UM Table 2 p.23)."""

    DET = "DET"  # deterministic: all successors
    PRO = "PRO"  # probabilistic: exactly one
    CFI = "CFI"  # conditional take-first
    CAL = "CAL"  # conditional take-all


class RankingRule(IntEnum):
    """Waiting-file ranking rule (POP f9, UM p.41)."""

    LOW_VALUE_FIRST = 1
    HIGH_VALUE_FIRST = 2
    FIFO = 3
    LIFO = 4

    @classmethod
    def _missing_(cls, value: object) -> RankingRule | None:
        aliases = {
            "LOW": cls.LOW_VALUE_FIRST, "LVF": cls.LOW_VALUE_FIRST,
            "HIGH": cls.HIGH_VALUE_FIRST, "HVF": cls.HIGH_VALUE_FIRST,
            "FIFO": cls.FIFO, "LIFO": cls.LIFO,
        }
        return aliases.get(str(value).upper())


class StatType(str, Enum):
    """Statistics-task type (STA f5, spec §4.4)."""

    FIR = "FIR"
    ALL = "ALL"
    BET = "BET"
    INT = "INT"
    NUM = "NUM"


class Timing(str, Enum):
    """Event points at which marks, assignments and statistics fire."""

    FPC = "FPC"  # first predecessor completion (MARK only)
    REL = "REL"
    STA = "STA"
    COM = "COM"
    CLR = "CLR"  # clearing (not produced in Step 1; accepted for schema stability)


class IncomingRule(str, Enum):
    """INCM: which predecessor packet a released task keeps."""

    FIRST = "FIRST"
    LAST = "LAST"
    BIG = "BIG"
    SMALL = "SMALL"


class ValueKind(str, Enum):
    """Value-reference function types (spec §4.1) plus inline DIST."""

    DS = "DS"  # distribution set n
    SC = "SC"  # constant (divided by general.scale)
    UF = "UF"  # user function n
    IA = "IA"  # information attribute of the packet
    SA = "SA"  # system attribute
    DIST = "DIST"  # inline distribution (pySAINT extension)


class AttrType(str, Enum):
    """Attribute source for conditions / assignment targets."""

    IA = "IA"
    SA = "SA"


class DistType(str, Enum):
    """Distribution codes (DIS f3, UM p.45-46) plus EX (exponential extension)."""

    CO = "CO"
    NO = "NO"
    LO = "LO"
    BE = "BE"
    GA = "GA"
    UN = "UN"
    ER = "ER"
    PO = "PO"
    BP = "BP"
    TR = "TR"
    WE = "WE"
    EX = "EX"

    @classmethod
    def _missing_(cls, value: object) -> DistType | None:
        aliases = {
            "CONSTANT": cls.CO, "NORMAL": cls.NO, "LOGNORMAL": cls.LO, "BETA": cls.BE,
            "GAMMA": cls.GA, "UNIFORM": cls.UN, "ERLANG": cls.ER, "POISSON": cls.PO,
            "PERT": cls.BP, "BETA-PERT": cls.BP, "TRIANGULAR": cls.TR, "WEIBULL": cls.WE,
            "EXPONENTIAL": cls.EX,
        }
        return aliases.get(str(value).upper())


class CondCode(str, Enum):
    """Conditional branch codes (UM Table 4 p.25)."""

    TLV = "TLV"
    TGV = "TGV"
    TLA = "TLA"
    TGA = "TGA"
    TVC = "TVC"
    TVN = "TVN"
    TAC = "TAC"
    TAN = "TAN"
    ALV = "ALV"
    AGV = "AGV"
    ALA = "ALA"
    AGA = "AGA"
    NO = "NO"
