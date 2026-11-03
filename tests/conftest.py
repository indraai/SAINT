from pathlib import Path

import pytest

import pysaint as ps

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "yaml"


def mk(tasks, **kw):
    """Build a Model from a tasks dict plus optional top-level sections."""
    return ps.Model.model_validate({"tasks": tasks, **kw})


@pytest.fixture
def examples():
    return EXAMPLES
