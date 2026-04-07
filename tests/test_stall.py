"""Tests for stall detection and speed trend."""

import time

import pytest

from chugchug._renderer import TrackerView
from chugchug._types import ProgressEvent, TrackerState


def _make_event(n: int, total: int = 100, elapsed: float = 1.0) -> ProgressEvent:
    return ProgressEvent(
        tracker_name="test",
        n=n,
        total=total,
        elapsed=elapsed,
        state=TrackerState.RUNNING,
    )


class TestStallDetection:
    def test_no_stall_when_progressing(self):
        view = TrackerView(name="test")
        view.apply_event(_make_event(n=10))
        view.apply_event(_make_event(n=20))
        assert view.stall_seconds == 0.0

    def test_stall_detected(self):
        view = TrackerView(name="test")
        view.apply_event(_make_event(n=10))
        view.last_progress_time = time.monotonic() - 15  # Fake 15s ago
        view.apply_event(_make_event(n=10))  # Same n
        assert view.stall_seconds >= 14

    def test_stall_resets_on_progress(self):
        view = TrackerView(name="test")
        view.apply_event(_make_event(n=10))
        view.last_progress_time = time.monotonic() - 20
        view.apply_event(_make_event(n=10))  # Stalled
        assert view.stall_seconds >= 19
        view.apply_event(_make_event(n=11))  # Progress!
        assert view.stall_seconds == 0.0


class TestSpeedTrend:
    def test_no_trend_with_few_samples(self):
        view = TrackerView(name="test")
        view.recent_rates = [10.0, 10.0]
        assert view.speed_trend == ""

    def test_accelerating(self):
        view = TrackerView(name="test")
        view.recent_rates = [10.0, 10.0, 10.0, 15.0, 15.0, 15.0]
        assert view.speed_trend == "\u2191"

    def test_decelerating(self):
        view = TrackerView(name="test")
        view.recent_rates = [15.0, 15.0, 15.0, 10.0, 10.0, 10.0]
        assert view.speed_trend == "\u2193"

    def test_steady(self):
        view = TrackerView(name="test")
        view.recent_rates = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
        assert view.speed_trend == "\u2192"
