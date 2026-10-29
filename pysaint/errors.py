"""Exception hierarchy and code tables.

Execution errors 3001-3604 map one-to-one to exception classes (spec §10.2);
input errors carry card and field locations (spec §10.1). Not yet implemented.
"""


class SaintError(Exception):
    """Base class for all pySAINT errors."""

    code: int | None = None


class SaintInputError(SaintError):
    """Problem found while reading or validating a model."""


class SaintExecutionError(SaintError):
    """Problem found while a simulation is running (codes 3001-3604)."""
