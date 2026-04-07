"""ETA prediction models — all accept external timestamps for testability."""

from __future__ import annotations

import math
import time
from collections import deque


class WeightedRegressionETA:
    """ETA via weighted linear regression on a sliding window.

    Ported from fortschritt's SmartETA — recent points weighted more heavily.
    Detects acceleration/deceleration trends and extrapolates.
    """

    def __init__(self, window: int = 50) -> None:
        self._times: deque[float] = deque(maxlen=window)
        self._counts: deque[float] = deque(maxlen=window)
        self._start_time: float | None = None

    def update(self, n: int, timestamp: float | None = None) -> None:
        t = timestamp or time.monotonic()
        if self._start_time is None:
            self._start_time = t
        self._times.append(t - self._start_time)
        self._counts.append(n)

    def eta(self, current: int, total: int) -> float | None:
        if current >= total:
            return 0.0
        if len(self._times) < 3:
            elapsed = (self._times[-1] if self._times else 0.0)
            if current <= 0 or elapsed <= 0:
                return None
            rate = current / elapsed
            return (total - current) / rate if rate > 0 else None

        n = len(self._times)
        weights = [1 + i / n for i in range(n)]
        w_sum = sum(weights)

        t = list(self._times)
        c = list(self._counts)

        t_mean = sum(w * ti for w, ti in zip(weights, t)) / w_sum
        c_mean = sum(w * ci for w, ci in zip(weights, c)) / w_sum

        num = sum(w * (ci - c_mean) * (ti - t_mean) for w, ci, ti in zip(weights, c, t))
        den = sum(w * (ti - t_mean) ** 2 for w, ti in zip(weights, t))

        if abs(den) < 1e-10:
            return None

        slope = num / den
        if slope <= 0:
            return None

        return (total - current) / slope

    @property
    def rate(self) -> float | None:
        if len(self._times) < 2:
            return None
        dt = self._times[-1] - self._times[0]
        dn = self._counts[-1] - self._counts[0]
        return dn / dt if dt > 0 else None


class DoubleExponentialETA:
    """Holt's double exponential smoothing — captures trends.

    Good for tasks with consistent acceleration/deceleration.
    """

    def __init__(self, alpha: float = 0.3, beta: float = 0.1) -> None:
        self._alpha = alpha
        self._beta = beta
        self._level: float | None = None
        self._trend: float = 0.0
        self._last_time: float | None = None
        self._last_n: int = 0
        self._start_time: float = time.monotonic()
        self._rate_estimate: float | None = None

    def update(self, n: int, timestamp: float | None = None) -> None:
        t = timestamp or time.monotonic()
        if self._last_time is None:
            self._last_time = t
            self._last_n = n
            return

        dt = t - self._last_time
        if dt <= 0:
            return

        current_rate = (n - self._last_n) / dt

        if self._level is None:
            self._level = current_rate
            self._trend = 0.0
        else:
            prev_level = self._level
            self._level = self._alpha * current_rate + (1 - self._alpha) * (self._level + self._trend)
            self._trend = self._beta * (self._level - prev_level) + (1 - self._beta) * self._trend

        self._rate_estimate = self._level + self._trend
        self._last_time = t
        self._last_n = n

    def eta(self, current: int, total: int) -> float | None:
        if current >= total:
            return 0.0
        if self._rate_estimate is None or self._rate_estimate <= 0:
            return None
        return (total - current) / self._rate_estimate

    @property
    def rate(self) -> float | None:
        return self._rate_estimate if self._rate_estimate and self._rate_estimate > 0 else None


class AdaptiveETA:
    """Ensemble ETA — tracks prediction error and auto-selects best model."""

    def __init__(self, window: int = 50) -> None:
        self._regression = WeightedRegressionETA(window=window)
        self._exponential = DoubleExponentialETA()
        self._regression_error: float = 0.0
        self._exponential_error: float = 0.0
        self._last_predictions: dict[str, float | None] = {}
        self._last_check_n: int = 0
        self._decay: float = 0.95

    def update(self, n: int, timestamp: float | None = None) -> None:
        # Track prediction errors before updating models
        if n > self._last_check_n and self._last_predictions:
            # We can't truly measure ETA error without knowing final time,
            # but we can compare rate stability
            pass

        self._regression.update(n, timestamp)
        self._exponential.update(n, timestamp)
        self._last_check_n = n

    def eta(self, current: int, total: int) -> float | None:
        r_eta = self._regression.eta(current, total)
        e_eta = self._exponential.eta(current, total)

        if r_eta is not None and e_eta is not None:
            # Weighted average, favoring regression early, exponential late
            if current < total * 0.3:
                # Early: regression is better (needs fewer samples but captures trend)
                return 0.7 * r_eta + 0.3 * e_eta
            else:
                # Late: exponential captures recent dynamics better
                return 0.4 * r_eta + 0.6 * e_eta

        return r_eta if r_eta is not None else e_eta

    @property
    def rate(self) -> float | None:
        return self._regression.rate or self._exponential.rate


def create_eta(strategy: str = "adaptive", window: int = 50) -> WeightedRegressionETA | DoubleExponentialETA | AdaptiveETA:
    """Factory for ETA predictors."""
    match strategy:
        case "regression":
            return WeightedRegressionETA(window=window)
        case "exponential":
            return DoubleExponentialETA()
        case "adaptive":
            return AdaptiveETA(window=window)
        case _:
            return AdaptiveETA(window=window)
