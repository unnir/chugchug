"""Tests for _eta.py — ETA prediction with synthetic data."""

import pytest

from chugchug._eta import (
    AdaptiveETA,
    DoubleExponentialETA,
    WeightedRegressionETA,
    create_eta,
)


class TestWeightedRegressionETA:
    def test_constant_rate(self):
        """Constant 10 items/sec should predict accurately."""
        eta = WeightedRegressionETA(window=50)
        # Simulate: 10 items/sec for 100 items
        for i in range(1, 51):
            eta.update(i, timestamp=i * 0.1)

        remaining_eta = eta.eta(50, 100)
        assert remaining_eta is not None
        # Should be approximately 5 seconds
        assert 4.0 < remaining_eta < 6.0

    def test_rate(self):
        eta = WeightedRegressionETA(window=50)
        for i in range(1, 21):
            eta.update(i, timestamp=i * 0.1)
        rate = eta.rate
        assert rate is not None
        assert 9.0 < rate < 11.0  # ~10 items/sec

    def test_completed(self):
        eta = WeightedRegressionETA()
        eta.update(100, timestamp=1.0)
        assert eta.eta(100, 100) == 0.0

    def test_few_samples_fallback(self):
        eta = WeightedRegressionETA()
        eta.update(5, timestamp=1.0)
        eta.update(10, timestamp=2.0)
        result = eta.eta(10, 100)
        assert result is not None
        assert result > 0

    def test_zero_progress(self):
        eta = WeightedRegressionETA()
        result = eta.eta(0, 100)
        assert result is None


class TestDoubleExponentialETA:
    def test_constant_rate(self):
        eta = DoubleExponentialETA()
        for i in range(1, 51):
            eta.update(i, timestamp=i * 0.1)

        remaining = eta.eta(50, 100)
        assert remaining is not None
        assert remaining > 0

    def test_rate(self):
        eta = DoubleExponentialETA()
        for i in range(1, 21):
            eta.update(i, timestamp=i * 0.1)
        assert eta.rate is not None
        assert eta.rate > 0


class TestAdaptiveETA:
    def test_constant_rate(self):
        eta = AdaptiveETA(window=50)
        for i in range(1, 51):
            eta.update(i, timestamp=i * 0.1)

        remaining = eta.eta(50, 100)
        assert remaining is not None
        assert 3.0 < remaining < 8.0

    def test_rate(self):
        eta = AdaptiveETA(window=50)
        for i in range(1, 21):
            eta.update(i, timestamp=i * 0.1)
        assert eta.rate is not None


class TestFactory:
    def test_create_regression(self):
        eta = create_eta("regression")
        assert isinstance(eta, WeightedRegressionETA)

    def test_create_exponential(self):
        eta = create_eta("exponential")
        assert isinstance(eta, DoubleExponentialETA)

    def test_create_adaptive(self):
        eta = create_eta("adaptive")
        assert isinstance(eta, AdaptiveETA)

    def test_create_default(self):
        eta = create_eta("unknown_strategy")
        assert isinstance(eta, AdaptiveETA)
