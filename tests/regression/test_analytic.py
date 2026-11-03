"""Analytic regression checks of the kernel."""

import pytest

import pysaint as ps
from tests.conftest import mk


def test_deterministic_serial_parallel_completion_times():
    # A(2) -> {B(3), C(5)} -> D(1, needs both) -> E sink.  Critical path 2+5+1 = 8.
    m = mk({
        1: {"label": "A", "role": "source", "time": 2, "branching": {"successors": [2, 3]}},
        2: {"label": "B", "time": 3, "branching": {"successors": [4]}},
        3: {"label": "C", "time": 5, "branching": {"successors": [4]}},
        4: {"label": "D", "pr1": 2, "time": 1, "branching": {"successors": [5]}},
        5: {"label": "E", "role": "sink"},
    })
    res = ps.Simulation(m).run(3)
    s = res.task_summary().set_index(["task", "stat"])["mean"]
    assert s[(1, "completion_time")] == 2
    assert s[(2, "completion_time")] == 5
    assert s[(3, "completion_time")] == 7
    assert s[(4, "completion_time")] == 8
    assert res.end_time().mean == 8 and res.end_time().sd == 0


def test_scale_factor():
    m = mk({1: {"role": "source", "time": 575, "branching": {"successors": [2]}},
            2: {"role": "sink"}}, general={"scale": 100})
    assert ps.Simulation(m).run(1).end_time().mean == pytest.approx(5.75)


def test_probabilistic_branch_frequency():
    m = mk({
        1: {"role": "source", "time": 1, "branching": {"type": "PRO", "branches": [
            {"to": 2, "p": 0.3}, {"to": 3, "p": 0.7}]}},
        2: {"role": "sink"}, 3: {"role": "sink"},
    }, general={"iterations": 4000})
    res = ps.Simulation(m, seed=99).run()
    c = res.task_counts()
    frac = c[c.task == 2].completions.mean()
    assert abs(frac - 0.3) < 3 * (0.3 * 0.7 / 4000) ** 0.5 + 0.005


def test_geometric_rework_count(examples):
    # INSPECT repeats until SHIP: N ~ Geometric(0.8) => E[N] = 1/0.8 = 1.25.
    m = ps.load_model(examples / "inspection_network.yaml")
    res = ps.Simulation(m, seed=5).run(4000)
    assert res.stat(4, "NUM-COM").mean == pytest.approx(1.25, abs=0.03)


def test_mm1_utilization_and_time_in_system():
    # lambda = 0.5, mu = 1 => rho = 0.5, W = 1/(mu - lambda) = 2.
    m = mk({
        1: {"label": "ARRIVE", "role": "source", "pr2": 1, "time": {"dist": {"type": "EX",
            "mean": 2.0}}, "branching": {"successors": [1, 2]}},
        2: {"label": "SERVE", "pr2": 1, "time": {"dist": {"type": "EX", "mean": 1.0}},
            "resources": {"ids": [1]}, "mark": {"at": "REL"},
            "branching": {"successors": [3]}},
        3: {"label": "DONE", "role": "sink", "pr2": 1, "stat": {"type": "INT", "at": "COM"}},
    }, resources={1: {}}, general={"sinks_to_complete": 5000, "iterations": 8})
    res = ps.Simulation(m, seed=2024).run()
    assert res.utilization(1).mean == pytest.approx(0.5, abs=0.02)
    assert res.stat(3, "INT-COM").mean == pytest.approx(2.0, rel=0.08)
    assert res.stat(1, "interval").mean == pytest.approx(2.0, rel=0.03)


def test_mm2_example(examples):
    # M/M/2, lambda = 0.8, mu = 0.5: rho = 0.8, W = 1/mu + Wq = 2 + 3.556 = 5.556.
    m = ps.load_model(examples / "two_operator_queue.yaml")
    res = ps.Simulation(m).run()
    u = (res.utilization(1).mean + res.utilization(2).mean) / 2
    assert u == pytest.approx(0.8, abs=0.03)
    assert res.stat(3, "INT-COM").mean == pytest.approx(5.556, rel=0.1)
