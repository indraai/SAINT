import pytest

import pysaint as ps
from pysaint.errors import NegativeTaskTimeError, NetworkDeadlockError
from pysaint.kernel.events import Calendar
from tests.conftest import mk


def test_calendar_order():
    c = Calendar()
    c.schedule(2.0, "late")
    c.schedule(1.0, "lowprec", prec=0)
    c.schedule(1.0, "hiprec", prec=5)
    c.schedule(1.0, "lowprec2", prec=0)
    assert [c.pop().payload for _ in range(4)] == ["hiprec", "lowprec", "lowprec2", "late"]


def first_start(res, task):
    return next(r["value"] for r in res.obs_rows
            if r["task"] == task and r["stat"] == "completion_time")


@pytest.mark.parametrize("rule,first", [("FIFO", 1), ("LIFO", 2), ("HIGH", 2), ("LOW", 1)])
def test_ranking_rules(rule, first):
    # Two sources contend for one resource; both released at t=0 in id order.
    m = mk({
        1: {"role": "source", "time": 3, "priority": 1, "resources": {"ids": [1]},
            "branching": {"successors": [3]}},
        2: {"role": "source", "time": 4, "priority": 5, "resources": {"ids": [1]},
            "branching": {"successors": [3]}},
        3: {"role": "sink", "pr1": 2},
    }, resources={1: {}}, options={"ranking": rule})
    res = ps.Simulation(m).run(1)
    other = 2 if first == 1 else 1
    dur = {1: 3, 2: 4}
    assert first_start(res, first) == dur[first]
    assert first_start(res, other) == 7
    assert res.iteration_rows[0]["end_time"] == 7
    assert res.utilization(1).mean == pytest.approx(1.0)


def test_or_resources_pick_lowest_idle():
    m = mk({
        1: {"role": "source", "time": 2, "resources": {"mode": "OR", "ids": [1, 2]},
            "branching": {"successors": [3]}},
        2: {"role": "source", "time": 2, "resources": {"mode": "OR", "ids": [1, 2]},
            "branching": {"successors": [3]}},
        3: {"role": "sink", "pr1": 2},
    }, resources={1: {}, 2: {}})
    res = ps.Simulation(m).run(1)
    assert res.iteration_rows[0]["end_time"] == 2  # parallel on two operators
    assert [r["n_tasks"] for r in res.resource_rows] == [1, 1]


def test_diff_only_counts_distinct_predecessors():
    # Task 1 completes twice (self loop) before 2 completes; 3 needs 2 distinct preds.
    m = mk({
        1: {"role": "source", "pr2": 1, "time": 1, "branching": {"type": "CFI", "branches": [
            {"to": 1, "condition": {"code": "TLV", "value": 1.5}},
            {"to": 3, "condition": {"code": "NO"}}]}},
        4: {"role": "source", "time": 1, "branching": {"successors": [3]}},
        2: {"role": "source", "time": 5, "branching": {"successors": [3]}},
        3: {"role": "sink", "pr1": 2, "diff": True},
    })
    # 1 completes at t=1 (loops), t=2 (-> 3); 4 completes at t=1 (-> 3) => release at 2.
    res = ps.Simulation(m).run(1)
    assert res.iteration_rows[0]["end_time"] == 2


def test_conditional_take_all_and_attributes():
    m = mk({
        1: {"role": "source", "time": 1,
            "assignments": [{"at": "COM", "target": "IA", "index": 1, "value": 7}],
            "branching": {"type": "CAL", "branches": [
                {"to": 2, "condition": {"code": "AGV", "attr": 1, "value": 5}},
                {"to": 3, "condition": {"code": "ALV", "attr": 1, "value": 5}},
                {"to": 4, "condition": {"code": "TGV", "value": 0.5}}]}},
        2: {"role": "sink"}, 3: {"role": "sink"}, 4: {"role": "sink"},
    }, general={"sinks_to_complete": 0})
    res = ps.Simulation(m).run(1)
    done = {r["task"] for r in res.count_rows if r["completions"]}
    assert done == {1, 2, 4}


def test_errors():
    m = mk({1: {"role": "source", "time": -1}, 2: {"role": "sink"}})
    with pytest.raises(NegativeTaskTimeError):
        ps.Simulation(m).run(1)
    m = mk({1: {"role": "source", "time": 1}, 2: {"role": "sink"}})
    with pytest.raises(NetworkDeadlockError) as e:
        ps.Simulation(m).run(1)
    assert e.value.code == 3010


def test_reproducible_and_seed_sensitive(examples):
    m = ps.load_model(examples / "inspection_network.yaml")
    a = ps.Simulation(m, seed=1).run(20).iteration_rows
    b = ps.Simulation(m, seed=1).run(20).iteration_rows
    c = ps.Simulation(m, seed=2).run(20).iteration_rows
    assert a == b and a != c
    # iteration i is independent of total iteration count
    assert ps.Simulation(m, seed=1).run(5).iteration_rows == a[:5]


def test_max_time_limit():
    m = mk({1: {"role": "source", "pr2": 1, "time": 1, "branching": {"successors": [1]}},
            2: {"role": "sink"}}, general={"max_time": 10.5})
    res = ps.Simulation(m).run(1)
    assert res.iteration_rows[0]["end_time"] == 10.5 and res.warnings


def test_userf():
    m = mk({1: {"role": "source", "time": {"UF": 3}, "branching": {"successors": [2]}},
            2: {"role": "sink"}})
    res = ps.Simulation(m, userf={3: lambda ctx, n: 2.0 * n}).run(1)
    assert res.iteration_rows[0]["end_time"] == 6
