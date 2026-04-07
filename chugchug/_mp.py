"""Queue-based multiprocessing — spawn-safe, no shared locks.

RemoteTracker puts events on a queue (never blocks).
QueueListener drains the queue in the parent process.
MPContext is the user-facing context manager.
"""

from __future__ import annotations

import multiprocessing
import threading
import time
from multiprocessing import Queue
from typing import Any

from ._types import HandlerProtocol, ProgressEvent, TrackerState
from ._tracker import Registry, get_registry


class RemoteTracker:
    """Picklable proxy tracker — puts events on a queue.

    Used in child processes. Events carry absolute `n` so dropped
    events self-heal (the handler sees the latest state regardless).
    """

    def __init__(
        self,
        name: str,
        queue: Queue,
        total: int | None = None,
        desc: str = "",
    ) -> None:
        self._name = name
        self._queue = queue
        self._total = total
        self._desc = desc
        self._n = 0
        self._metrics: dict[str, str] = {}
        self._start_time = time.monotonic()

    @property
    def name(self) -> str:
        return self._name

    @property
    def n(self) -> int:
        return self._n

    @property
    def total(self) -> int | None:
        return self._total

    def update(self, n: int = 1) -> None:
        self._n += n
        event = ProgressEvent(
            tracker_name=self._name,
            n=self._n,
            total=self._total,
            elapsed=time.monotonic() - self._start_time,
            desc=self._desc,
            metrics=tuple(self._metrics.items()),
            state=TrackerState.RUNNING,
        )
        try:
            self._queue.put_nowait(event)
        except Exception:
            # Queue full — drop event. Absolute `n` means next event self-heals.
            pass

    def set_description(self, desc: str) -> None:
        self._desc = desc

    def set_metrics(self, **kwargs: str) -> None:
        self._metrics.update(kwargs)

    def complete(self) -> None:
        if self._total is not None:
            self._n = self._total
        self._send_state(TrackerState.COMPLETED)

    def close(self) -> None:
        self._send_state(TrackerState.COMPLETED)

    def _send_state(self, state: TrackerState) -> None:
        event = ProgressEvent(
            tracker_name=self._name,
            n=self._n,
            total=self._total,
            elapsed=time.monotonic() - self._start_time,
            desc=self._desc,
            metrics=tuple(self._metrics.items()),
            state=state,
        )
        try:
            self._queue.put_nowait(event)
        except Exception:
            pass


_SENTINEL = None  # Signals the listener to stop


class QueueListener:
    """Daemon thread in the parent process — drains queue to registry."""

    def __init__(self, queue: Queue, registry: Registry | None = None) -> None:
        self._queue = queue
        self._registry = registry or get_registry()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                event = self._queue.get(timeout=0.1)
                if event is _SENTINEL:
                    break
                self._registry.dispatch(event)
                if event.state == TrackerState.COMPLETED:
                    self._registry.close_tracker(event.tracker_name)
            except Exception:
                # queue.Empty or other — continue
                continue

    def stop(self) -> None:
        self._stop_event.set()
        try:
            self._queue.put_nowait(_SENTINEL)
        except Exception:
            pass
        if self._thread:
            self._thread.join(timeout=2.0)


class MPContext:
    """Context manager for multiprocessing progress.

    Usage:
        with MPContext() as ctx:
            with ProcessPoolExecutor() as pool:
                futures = []
                for i in range(4):
                    t = ctx.tracker(f"worker-{i}", total=100)
                    futures.append(pool.submit(work, t))
    """

    def __init__(
        self,
        maxsize: int = 10000,
        registry: Registry | None = None,
        context: str = "spawn",
    ) -> None:
        mp_ctx = multiprocessing.get_context(context)
        self._queue: Queue = mp_ctx.Queue(maxsize=maxsize)
        self._registry = registry or get_registry()
        self._listener = QueueListener(self._queue, self._registry)

    def tracker(
        self,
        name: str,
        total: int | None = None,
        desc: str = "",
    ) -> RemoteTracker:
        """Create a picklable tracker for use in a child process."""
        return RemoteTracker(name, self._queue, total=total, desc=desc)

    @property
    def queue(self) -> Queue:
        return self._queue

    def __enter__(self) -> MPContext:
        self._listener.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self._listener.stop()
