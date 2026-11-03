import pytest

import pysaint as ps
from pysaint.errors import ModelValidationError
from tests.conftest import mk


def codes(m):
    return {d.code for d in ps.validate(m).diagnostics}


def test_valid_model_ok():
    m = mk({1: {"role": "source", "branching": {"successors": [2]}}, 2: {"role": "sink"}})
    assert ps.validate(m).ok and not codes(m)


def test_cross_reference_errors():
    m = mk({
        1: {"role": "source", "time": {"DS": 9}, "resources": {"ids": [7]},
            "branching": {"successors": [42]}},
        2: {"role": "sink"},
    })
    assert {"I401", "I402", "I403", "I506"} <= codes(m)


def test_probability_errors():
    base = {2: {"role": "sink"}, 3: {"role": "sink"}}
    m = mk({1: {"role": "source", "branching": {"type": "PRO", "branches": [
        {"to": 2, "p": 0.5}, {"to": 3, "p": 0.4}]}}, **base})
    assert "I501" in codes(m)
    m = mk({1: {"role": "source", "branching": {"type": "PRO", "branches": [
        {"to": 2, "p": -0.5}, {"to": 3, "p": 1.5}]}}, **base})
    assert "I502" in codes(m)


def test_no_source_no_sink_and_cfi_order():
    assert {"I503", "I504"} <= codes(mk({1: {"pr1": 1}}))
    m = mk({1: {"role": "source", "branching": {"type": "CFI", "branches": [
        {"to": 2, "condition": {"code": "NO"}},
        {"to": 2, "condition": {"code": "TLV", "value": 3}}]}}, 2: {"role": "sink"}})
    assert "I505" in codes(m)


def test_bad_distribution_and_simulation_refuses():
    m = mk({1: {"role": "source", "time": {"DS": 1}}},
           distributions={1: {"type": "UN", "min": 5, "max": 1}}, general={"sinks_to_complete": 0})
    assert "I201" in codes(m)
    with pytest.raises(ModelValidationError):
        ps.Simulation(m)
