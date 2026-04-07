"""Tests for _tracker.py — event dispatch and registry behavior."""

import pytest

from chugchug._tracker import Registry, Tracker, get_registry, tracker
from chugchug._types import ProgressEvent, TrackerState


class MockHandler:
    """Captures events for testing."""

    def __init__(self):
        self.events: list[ProgressEvent] = []
        self.closed: list[str] = []

    def on_event(self, event: ProgressEvent) -> None:
        self.events.append(event)

    def on_close(self, tracker_name: str) -> None:
        self.closed.append(tracker_name)


class TestTracker:
    def test_basic_update(self):
        reg = Registry()
        handler = MockHandler()
        reg.add_handler(handler)

        t = Tracker("test", total=100, registry=reg)
        t.update(10)

        assert len(handler.events) == 1
        assert handler.events[0].n == 10
        assert handler.events[0].total == 100

    def test_multiple_updates(self):
        reg = Registry()
        handler = MockHandler()
        reg.add_handler(handler)

        t = Tracker("test", total=50, registry=reg)
        t.update(10)
        t.update(5)
        t.update(20)

        assert len(handler.events) == 3
        assert handler.events[-1].n == 35

    def test_set_description(self):
        reg = Registry()
        handler = MockHandler()
        reg.add_handler(handler)

        t = Tracker("test", registry=reg)
        t.set_description("New desc")
        t.update()

        assert handler.events[0].desc == "New desc"

    def test_set_metrics(self):
        reg = Registry()
        handler = MockHandler()
        reg.add_handler(handler)

        t = Tracker("test", registry=reg)
        t.set_metrics(loss="0.5", acc="0.9")
        t.update()

        metrics = handler.events[0].metrics_dict
        assert metrics["loss"] == "0.5"
        assert metrics["acc"] == "0.9"

    def test_complete(self):
        reg = Registry()
        handler = MockHandler()
        reg.add_handler(handler)

        t = Tracker("test", total=100, registry=reg)
        t.update(50)
        t.complete()

        assert handler.events[-1].n == 100
        assert handler.events[-1].state == TrackerState.COMPLETED

    def test_close(self):
        reg = Registry()
        handler = MockHandler()
        reg.add_handler(handler)

        t = Tracker("test", registry=reg)
        t.update()
        t.close()

        assert "test" in handler.closed

    def test_reset(self):
        reg = Registry()
        t = Tracker("test", total=100, registry=reg)
        t.update(50)
        t.reset(total=200)

        assert t.n == 0
        assert t.total == 200
        assert t.state == TrackerState.IDLE


class TestRegistry:
    def test_add_remove_handler(self):
        reg = Registry()
        handler = MockHandler()

        reg.add_handler(handler)
        assert len(reg.handlers) == 1

        reg.remove_handler(handler)
        assert len(reg.handlers) == 0

    def test_get_tracker_creates_new(self):
        reg = Registry()
        t = reg.get_tracker("test", total=100)
        assert t.name == "test"
        assert t.total == 100

    def test_get_tracker_returns_existing(self):
        reg = Registry()
        t1 = reg.get_tracker("test")
        t2 = reg.get_tracker("test")
        assert t1 is t2

    def test_dispatch_to_multiple_handlers(self):
        reg = Registry()
        h1 = MockHandler()
        h2 = MockHandler()
        reg.add_handler(h1)
        reg.add_handler(h2)

        t = Tracker("test", registry=reg)
        t.update()

        assert len(h1.events) == 1
        assert len(h2.events) == 1

    def test_close_tracker_removes_from_registry(self):
        reg = Registry()
        handler = MockHandler()
        reg.add_handler(handler)

        t = reg.get_tracker("test")
        t.close()

        assert "test" not in reg.trackers

    def test_clear(self):
        reg = Registry()
        reg.add_handler(MockHandler())
        reg.get_tracker("test")
        reg.clear()

        assert len(reg.handlers) == 0
        assert len(reg.trackers) == 0
