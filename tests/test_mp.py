"""Tests for _mp.py — multiprocessing integration."""

import multiprocessing
from queue import Full
import time

import pytest

from chugchug._mp import MPContext, QueueListener, RemoteTracker
from chugchug._tracker import Registry
from chugchug._types import ProgressEvent, TrackerState


class MockHandler:
    def __init__(self):
        self.events: list[ProgressEvent] = []
        self.closed: list[str] = []

    def on_event(self, event: ProgressEvent) -> None:
        self.events.append(event)

    def on_close(self, tracker_name: str) -> None:
        self.closed.append(tracker_name)


def _worker_fn(tracker: RemoteTracker) -> None:
    """Simple worker function for spawn context."""
    for i in range(10):
        tracker.update(1)
    tracker.close()


class TestRemoteTracker:
    def test_basic_operations(self):
        q = multiprocessing.Queue(maxsize=100)
        tracker = RemoteTracker("test", q, total=10)

        tracker.update(1)
        tracker.set_description("new desc")
        tracker.set_metrics(loss="0.5")
        tracker.update(1)

        # Drain queue — allow a small delay for the queue
        import time
        time.sleep(0.1)
        events = []
        while not q.empty():
            events.append(q.get_nowait())

        assert len(events) == 2
        assert events[0].n == 1
        assert events[1].n == 2

    def test_complete(self):
        q = multiprocessing.Queue(maxsize=100)
        tracker = RemoteTracker("test", q, total=10)

        tracker.complete()

        import time
        time.sleep(0.1)
        event = q.get(timeout=1.0)
        assert event.n == 10
        assert event.state == TrackerState.COMPLETED

    def test_properties(self):
        q = multiprocessing.Queue(maxsize=100)
        tracker = RemoteTracker("test", q, total=50)

        assert tracker.name == "test"
        assert tracker.n == 0
        assert tracker.total == 50

    def test_complete_retries_when_queue_is_full(self):
        class FlakyQueue:
            def __init__(self):
                self.events = []

            def put_nowait(self, event):
                raise Full

            def put(self, event, timeout=None):
                self.events.append(event)

        q = FlakyQueue()
        tracker = RemoteTracker("test", q, total=10)

        tracker.complete()

        assert len(q.events) == 1
        assert q.events[0].state == TrackerState.COMPLETED


class TestQueueListener:
    def test_drains_events(self):
        mp_ctx = multiprocessing.get_context("spawn")
        q = mp_ctx.Queue(maxsize=100)
        reg = Registry()
        handler = MockHandler()
        reg.add_handler(handler)

        listener = QueueListener(q, reg)
        listener.start()

        # Put events on queue
        for i in range(5):
            event = ProgressEvent(tracker_name="test", n=i + 1, total=5)
            q.put(event)

        time.sleep(0.5)
        listener.stop()

        assert len(handler.events) >= 3  # At least some events processed

    def test_stop_drains_pending_events(self):
        mp_ctx = multiprocessing.get_context("spawn")
        q = mp_ctx.Queue(maxsize=100)
        reg = Registry()
        handler = MockHandler()
        reg.add_handler(handler)

        listener = QueueListener(q, reg)
        listener.start()

        q.put(ProgressEvent(tracker_name="test", n=1, total=1))
        listener.stop()

        assert handler.events
        assert handler.events[0].n == 1


class TestMPContext:
    def test_context_manager(self):
        reg = Registry()
        handler = MockHandler()
        reg.add_handler(handler)

        with MPContext(registry=reg) as ctx:
            tracker = ctx.tracker("test", total=10, desc="Testing")
            assert isinstance(tracker, RemoteTracker)
            assert tracker.name == "test"

    @pytest.mark.slow
    def test_with_process_pool(self):
        """Integration test with ProcessPoolExecutor using fork context."""
        import sys
        if sys.platform == "darwin":
            pytest.skip("fork may not work reliably on macOS")

        reg = Registry()
        handler = MockHandler()
        reg.add_handler(handler)

        with MPContext(registry=reg) as ctx:
            trackers = [ctx.tracker(f"worker-{i}", total=10) for i in range(2)]
            # Use fork context so Queue is inherited, not pickled
            mp_context = multiprocessing.get_context("fork")
            with mp_context.Pool(2) as pool:
                pool.map(_worker_fn, trackers)

            time.sleep(1.0)

        assert len(handler.events) > 0
