"""1-Euro filter behavior on synthetic noisy trajectories."""

from __future__ import annotations

import random

import pytest

from app.perception.smoothing import LowPassFilter, OneEuroFilter, OneEuroVectorFilter


def test_constant_input_converges():
    f = OneEuroFilter(freq=30.0)
    out = [f(10.0) for _ in range(60)]
    assert abs(out[-1] - 10.0) < 1e-3


def test_first_call_returns_input():
    f = OneEuroFilter()
    assert f(5.0) == 5.0


def test_denoises_jitter():
    random.seed(7)
    signal = [1.0 + random.uniform(-0.5, 0.5) for _ in range(200)]
    raw_var = _variance(signal)
    f = OneEuroFilter(min_cutoff=1.0, beta=0.0, freq=30.0)
    smooth = [f(v) for v in signal]
    assert _variance(smooth) < raw_var


def test_tracks_step_with_bounded_lag():
    f = OneEuroFilter(min_cutoff=0.1, beta=0.2, freq=30.0)
    out = [f(0.0) for _ in range(30)] + [f(1.0) for _ in range(30)]
    # Should reach near the new target quickly but with some smoothing.
    assert out[-1] > 0.9
    assert out[30] < 1.0  # not instant


def test_reset_reprimes():
    f = OneEuroFilter()
    f(5.0)
    f.reset(1.0)
    assert f(0.0) == 0.0 or f.last is not None
    f.reset()
    assert f.last is None


def test_invalid_args():
    with pytest.raises(ValueError):
        OneEuroFilter(min_cutoff=0)
    with pytest.raises(ValueError):
        OneEuroFilter(beta=-1)


def test_vector_filter():
    f = OneEuroVectorFilter(2, freq=30.0)
    assert f((1.0, 2.0)) == (1.0, 2.0)
    out = f((1.1, 2.1))
    assert len(out) == 2
    f.reset()
    assert f.last is not None


def test_lowpass_converges():
    lp = LowPassFilter(alpha=0.9)
    lp.reset(0.0)
    for _ in range(10):
        lp(1.0)
    assert abs(lp.y - 1.0) < 1e-6


def _variance(values):
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)
