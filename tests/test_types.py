"""Tests for _types.py — ProgressEvent pickling, protocols, enums."""

import pickle
import time

import pytest

from chugchug._types import (
    DiagnosticKind,
    HandlerProtocol,
    OutputMode,
    ProgressEvent,
    TrackerProtocol,
    TrackerState,
)


class TestProgressEvent:
    def test_creation(self):
        e = ProgressEvent(tracker_name="test", n=42, total=100)
        assert e.tracker_name == "test"
        assert e.n == 42
        assert e.total == 100

    def test_frozen(self):
        e = ProgressEvent(tracker_name="test", n=0)
        with pytest.raises(AttributeError):
            e.n = 10  # type: ignore

    def test_fraction(self):
        e = ProgressEvent(tracker_name="t", n=50, total=100)
        assert e.fraction == 0.5

    def test_fraction_none_total(self):
        e = ProgressEvent(tracker_name="t", n=50, total=None)
        assert e.fraction is None

    def test_fraction_zero_total(self):
        e = ProgressEvent(tracker_name="t", n=0, total=0)
        assert e.fraction is None

    def test_metrics_dict(self):
        e = ProgressEvent(
            tracker_name="t",
            n=0,
            metrics=(("loss", "0.5"), ("acc", "0.9")),
        )
        assert e.metrics_dict == {"loss": "0.5", "acc": "0.9"}

    def test_pickle_roundtrip(self):
        e = ProgressEvent(
            tracker_name="worker-1",
            n=42,
            total=100,
            elapsed=1.5,
            desc="Processing",
            metrics=(("loss", "0.5"),),
            state=TrackerState.RUNNING,
            parent="pipeline",
        )
        data = pickle.dumps(e)
        e2 = pickle.loads(data)
        assert e2.tracker_name == "worker-1"
        assert e2.n == 42
        assert e2.total == 100
        assert e2.metrics_dict == {"loss": "0.5"}
        assert e2.state == TrackerState.RUNNING

    def test_pickle_all_protocols(self):
        """Pickle with various pickle protocols."""
        e = ProgressEvent(tracker_name="t", n=10, total=50)
        for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
            data = pickle.dumps(e, protocol=protocol)
            e2 = pickle.loads(data)
            assert e2.n == 10


class TestEnums:
    def test_output_mode_values(self):
        assert OutputMode.TTY.value == "tty"
        assert OutputMode.JSON.value == "json"
        assert OutputMode.LOG.value == "log"
        assert OutputMode.SILENT.value == "silent"
        assert OutputMode.NOTEBOOK.value == "notebook"

    def test_tracker_state_values(self):
        assert TrackerState.IDLE.value == "idle"
        assert TrackerState.RUNNING.value == "running"
        assert TrackerState.COMPLETED.value == "completed"

    def test_diagnostic_kind_values(self):
        assert DiagnosticKind.CPU_BOUND.value == "cpu_bound"
        assert DiagnosticKind.IO_BOUND.value == "io_bound"
