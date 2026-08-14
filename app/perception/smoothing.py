"""1-Euro filter: low-latency noise smoothing (Casiez et al.).

Recommended defaults from 04_GESTURE_VOCABULARY: ``min_cutoff=1.0``,
``beta=0.007``. The 1-Euro filter adapts its cutoff based on velocity so a
slow, steady hand stays stable while a fast movement keeps up with minimal
lag — exactly what a gesture-controlled cursor needs.

Pure math, no I/O: fully unit-testable with synthetic trajectories.
"""

from __future__ import annotations

import time


class LowPassFilter:
    """Single-pole low-pass filter: ``y += alpha * (x - y)``."""

    def __init__(self, alpha: float):
        self.alpha = alpha
        self.y = None

    def reset(self, value: float | None = None) -> None:
        self.y = value

    def __call__(self, value: float) -> float:
        if self.y is None:
            self.y = value
            return value
        self.y = self.y + self.alpha * (value - self.y)
        return self.y


class OneEuroFilter:
    """Adaptive low-pass filter that trades jitter for lag by velocity.

    Args:
        min_cutoff: cutoff (Hz) for the low-speed case; larger = more lag,
            smaller = more jitter rejection.
        beta: how much the cutoff grows with speed; larger = more responsive
            to fast motion, 0 = plain fixed low-pass at ``min_cutoff``.
        d_cutoff: cutoff for the derivative (velocity) low-pass.
        freq: expected sampling frequency in Hz, used when a timestamp is
            not supplied to ``__call__``.
    """

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
        freq: float = 30.0,
    ):
        if min_cutoff <= 0 or d_cutoff <= 0 or freq <= 0:
            raise ValueError("cutoffs and freq must be positive")
        if beta < 0:
            raise ValueError("beta must be >= 0")
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self.freq = float(freq)
        self._x_filter = LowPassFilter(self._alpha(self.min_cutoff))
        self._dx_filter = LowPassFilter(self._alpha(self.d_cutoff))
        self._t_last: float | None = None

    def _alpha(self, cutoff: float) -> float:
        tau = 1.0 / (2.0 * 3.14159265 * cutoff)
        return 1.0 / (1.0 + tau * (1.0 / self.freq))

    def reset(self, value: float | None = None) -> None:
        self._x_filter.reset(value)
        self._dx_filter.reset(0.0)
        self._t_last = None

    def __call__(self, value: float, t: float | None = None) -> float:
        if t is None:
            t = (
                self._t_last + 1.0 / self.freq
                if self._t_last is not None
                else time.monotonic()
            )
        dt = (t - self._t_last) if self._t_last is not None else (1.0 / self.freq)
        if dt <= 0:
            dt = 1.0 / self.freq

        if self._x_filter.y is None:
            self._x_filter.reset(value)
            self._dx_filter.reset(0.0)
            self._t_last = t
            return value

        dx = (value - self._x_filter.y) / dt
        dx_hat = self._dx_filter(dx)
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        x_hat = self._x_filter.y + self._alpha(cutoff) * (value - self._x_filter.y)
        self._x_filter.y = x_hat
        self._t_last = t
        return x_hat

    @property
    def last(self) -> float | None:
        return self._x_filter.y


class OneEuroVectorFilter:
    """Convenience wrapper running one 1-Euro filter per coordinate."""

    def __init__(self, dims: int = 2, **kwargs):
        self.filters = [OneEuroFilter(**kwargs) for _ in range(dims)]

    def reset(self, values: tuple[float, ...] | None = None) -> None:
        for i, f in enumerate(self.filters):
            f.reset(values[i] if values else None)

    def __call__(self, values) -> tuple[float, ...]:
        return tuple(f(v) for f, v in zip(self.filters, values))

    @property
    def last(self) -> tuple[float | None, ...]:
        return tuple(f.last for f in self.filters)
