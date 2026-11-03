import numpy as np
import pytest

from pysaint.errors import DistributionArgumentError
from pysaint.kernel import rng
from pysaint.model.schema import Distribution

N = 20000
CASES = [  # (params, expected mean, tolerance)
    ({"type": "CO", "value": 3.0}, 3.0, 1e-12),
    ({"type": "UN", "min": 2, "max": 4}, 3.0, 0.03),
    ({"type": "NO", "mean": 10, "sd": 2}, 10.0, 0.06),
    ({"type": "EX", "mean": 2}, 2.0, 0.06),
    ({"type": "ER", "mean": 1, "k": 3}, 3.0, 0.06),
    ({"type": "TR", "mode": 2, "min": 1, "max": 6}, 3.0, 0.04),
    ({"type": "LO", "mean": 5, "sd": 1}, 5.0, 0.04),
    ({"type": "GA", "mean": 4, "sd": 2}, 4.0, 0.06),
    ({"type": "BE", "mean": 3, "sd": 0.5, "min": 1, "max": 5}, 3.0, 0.02),
    ({"type": "BP", "mode": 4, "min": 1, "max": 10}, 4.5, 0.05),
    ({"type": "PO", "mean": 3, "min": 1}, 4.0, 0.06),
    ({"type": "WE", "alpha": 1.0, "shape": 1.0}, 1.0, 0.04),  # = exponential(1)
]


@pytest.mark.parametrize("params,mean,tol", CASES)
def test_means(params, mean, tol):
    d = Distribution.model_validate(params)
    g = np.random.default_rng(1)
    xs = np.array([rng.sample(d, g) for _ in range(N)])
    assert abs(xs.mean() - mean) <= tol * max(1.0, mean)


def test_clamping_and_normal_floor():
    g = np.random.default_rng(2)
    d = Distribution(type="NO", mean=5, sd=3, min=4, max=6)
    xs = [rng.sample(d, g) for _ in range(2000)]
    assert min(xs) == 4 and max(xs) == 6
    d0 = Distribution(type="NO", mean=0.5, sd=2)
    assert min(rng.sample(d0, g) for _ in range(2000)) == 0.0


def test_bad_params():
    with pytest.raises(DistributionArgumentError):
        rng.sample(Distribution(type="GA", mean=-1, sd=1), np.random.default_rng())
    assert rng.check(Distribution(type="TR", mode=9, min=1, max=2))


def test_streams_reproducible_and_independent():
    a = rng.iteration_streams(7, 3).time.random(5)
    b = rng.iteration_streams(7, 3).time.random(5)
    c = rng.iteration_streams(7, 4).time.random(5)
    assert np.array_equal(a, b) and not np.array_equal(a, c)
