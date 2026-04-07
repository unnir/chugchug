"""Tests for _renderer.py — capture output, verify formatting."""

import io
import json

import pytest

from chugchug._renderer import JSONHandler, LOGHandler, SilentHandler, TTYHandler
from chugchug._types import ProgressEvent, TrackerState


def _make_event(
    name: str = "test",
    n: int = 50,
    total: int | None = 100,
    elapsed: float = 1.0,
    desc: str = "Testing",
    metrics: tuple = (),
    state: TrackerState = TrackerState.RUNNING,
) -> ProgressEvent:
    return ProgressEvent(
        tracker_name=name,
        n=n,
        total=total,
        elapsed=elapsed,
        desc=desc,
        metrics=metrics,
        state=state,
    )


class TestJSONHandler:
    def test_output_valid_json(self):
        buf = io.StringIO()
        handler = JSONHandler(file=buf)

        handler.on_event(_make_event())

        output = buf.getvalue().strip()
        data = json.loads(output)
        assert data["tracker"] == "test"
        assert data["n"] == 50
        assert data["total"] == 100
        assert data["percentage"] == 50.0

    def test_output_without_total(self):
        buf = io.StringIO()
        handler = JSONHandler(file=buf)

        handler.on_event(_make_event(total=None))

        data = json.loads(buf.getvalue().strip())
        assert "percentage" not in data

    def test_multiple_events(self):
        buf = io.StringIO()
        handler = JSONHandler(file=buf)

        handler.on_event(_make_event(n=10))
        handler.on_event(_make_event(n=50))
        handler.on_event(_make_event(n=100))

        lines = buf.getvalue().strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[-1])["n"] == 100


class TestLOGHandler:
    def test_output_format(self):
        buf = io.StringIO()
        handler = LOGHandler(file=buf, min_interval=0)

        handler.on_event(_make_event())

        output = buf.getvalue()
        assert "Testing" in output
        assert "50.0%" in output

    def test_metrics_included(self):
        buf = io.StringIO()
        handler = LOGHandler(file=buf, min_interval=0)

        handler.on_event(_make_event(metrics=(("loss", "0.5"),)))

        output = buf.getvalue()
        assert "loss=0.5" in output

    def test_no_total(self):
        buf = io.StringIO()
        handler = LOGHandler(file=buf, min_interval=0)

        handler.on_event(_make_event(total=None, n=42))

        output = buf.getvalue()
        assert "42" in output


class TestSilentHandler:
    def test_no_output(self):
        handler = SilentHandler()
        # Should not raise
        handler.on_event(_make_event())
        handler.on_close("test")


class TestTTYHandler:
    def test_basic_render(self):
        buf = io.StringIO()
        handler = TTYHandler(
            file=buf,
            min_interval=0,
            bar_width=20,
        )
        handler.on_event(_make_event())

        output = buf.getvalue()
        # Should contain percentage and count
        assert "50.0%" in output
        assert "50/100" in output

    def test_metrics_displayed(self):
        buf = io.StringIO()
        handler = TTYHandler(
            file=buf,
            min_interval=0,
            bar_width=20,
        )
        handler.on_event(_make_event(metrics=(("loss", "0.5"),)))

        output = buf.getvalue()
        assert "loss=0.5" in output
