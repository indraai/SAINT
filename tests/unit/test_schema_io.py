import pytest
from pydantic import ValidationError

import pysaint as ps
from pysaint.io import json_io, yaml_io
from pysaint.model.enums import BranchType, RankingRule, Role, ValueKind


def test_yaml_examples_load(examples):
    for f in examples.glob("*.yaml"):
        m = ps.load_model(f)
        assert m.tasks and ps.validate(m).ok, f


def test_shorthands_and_ids():
    m = ps.Model.model_validate({
        "options": {"ranking": "HIGH"},
        "tasks": {
            1: {"role": "source", "time": 2.5, "branching": {"successors": [2]}},
            "2": {"role": "sink", "time": {"DS": 1}, "stat": {"type": "INT", "at": "COM"}},
        },
        "distributions": {1: {"type": "triangular", "mode": 2, "low": 1, "high": 3}},
    })
    assert m.options.ranking is RankingRule.HIGH_VALUE_FIRST
    assert m.tasks[1].role is Role.SOURCE and m.tasks[1].time.kind is ValueKind.SC
    assert m.tasks[2].id == 2 and m.tasks[2].time.kind is ValueKind.DS
    assert m.tasks[1].branching.type is BranchType.DET
    assert m.distributions[1].min == 1 and len(m.tasks[2].stat) == 1
    assert m.tasks[1].first_release_count == 0 and m.tasks[2].first_release_count == 1


def test_roundtrip(examples):
    m = ps.load_model(examples / "inspection_network.yaml")
    assert yaml_io.loads(yaml_io.dumps(m)) == m
    assert json_io.loads(json_io.dumps(m)) == m


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        ps.Model.model_validate({"tasks": {1: {"bogus": 1}}})
