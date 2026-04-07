"""Tracker + Registry — the protocol core.

Trackers produce ProgressEvents. The Registry dispatches them to handlers.
Lock-free on the hot path (update/dispatch). Locks only for mutations
(get_tracker, add_handler).
"""

from __future__ import annotations

import threading
import time
from typing import Any

from ._types import HandlerProtocol, ProgressEvent, TrackerState


class Tracker:
    """Named progress emitter — produces ProgressEvents."""

    __slots__ = (
        "_name", "_n", "_total", "_desc", "_metrics", "_state",
        "_start_time", "_parent", "_registry",
    )

    def __init__(
        self,
        name: str,
        total: int | None = None,
        desc: str = "",
        parent: str | None = None,
        registry: Registry | None = None,
    ) -> None:
        self._name = name
        self._n = 0
        self._total = total
        self._desc = desc
        self._metrics: dict[str, str] = {}
        self._state = TrackerState.IDLE
        self._start_time = time.monotonic()
        self._parent = parent
        self._registry = registry or get_registry()

    @property
    def name(self) -> str:
        return self._name

    @property
    def n(self) -> int:
        return self._n

    @property
    def total(self) -> int | None:
        return self._total

    @total.setter
    def total(self, value: int | None) -> None:
        self._total = value

    @property
    def state(self) -> TrackerState:
        return self._state

    def _make_event(self) -> ProgressEvent:
        return ProgressEvent(
            tracker_name=self._name,
            n=self._n,
            total=self._total,
            elapsed=time.monotonic() - self._start_time,
            desc=self._desc,
            metrics=tuple(self._metrics.items()),
            state=self._state,
            parent=self._parent,
        )

    def update(self, n: int = 1) -> None:
        if self._state == TrackerState.IDLE:
            self._state = TrackerState.RUNNING
        self._n += n
        self._registry.dispatch(self._make_event())

    def set_description(self, desc: str) -> None:
        self._desc = desc

    def set_metrics(self, **kwargs: str) -> None:
        self._metrics.update(kwargs)

    def complete(self) -> None:
        if self._total is not None:
            self._n = self._total
        self._state = TrackerState.COMPLETED
        self._registry.dispatch(self._make_event())

    def close(self) -> None:
        if self._state != TrackerState.COMPLETED:
            self._state = TrackerState.COMPLETED
        self._registry.dispatch(self._make_event())
        self._registry.close_tracker(self._name)

    def reset(self, total: int | None = None) -> None:
        self._n = 0
        self._start_time = time.monotonic()
        self._metrics.clear()
        self._state = TrackerState.IDLE
        if total is not None:
            self._total = total


class Registry:
    """Global event dispatcher. Lock-free dispatch, locked mutations."""

    def __init__(self) -> None:
        self._handlers: list[HandlerProtocol] = []
        self._trackers: dict[str, Tracker] = {}
        self._lock = threading.Lock()

    def add_handler(self, handler: HandlerProtocol) -> None:
        with self._lock:
            self._handlers.append(handler)

    def remove_handler(self, handler: HandlerProtocol) -> None:
        with self._lock:
            self._handlers = [h for h in self._handlers if h is not handler]

    def get_tracker(
        self,
        name: str,
        total: int | None = None,
        desc: str = "",
        parent: str | None = None,
    ) -> Tracker:
        with self._lock:
            if name in self._trackers:
                return self._trackers[name]
            t = Tracker(name, total=total, desc=desc, parent=parent, registry=self)
            self._trackers[name] = t
            return t

    def dispatch(self, event: ProgressEvent) -> None:
        """Hot path — no locks. Reads a snapshot of the handler list."""
        handlers = self._handlers
        for handler in handlers:
            handler.on_event(event)

    def close_tracker(self, name: str) -> None:
        handlers = self._handlers
        for handler in handlers:
            handler.on_close(name)
        with self._lock:
            self._trackers.pop(name, None)

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()
            self._trackers.clear()

    @property
    def handlers(self) -> list[HandlerProtocol]:
        return list(self._handlers)

    @property
    def trackers(self) -> dict[str, Tracker]:
        return dict(self._trackers)


# ─── Module-level singleton ──────────────────────────────────────────────────

_registry: Registry | None = None
_registry_lock = threading.Lock()


def get_registry() -> Registry:
    """Get the global registry singleton."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = Registry()
    return _registry


def tracker(name: str, **kwargs: Any) -> Tracker:
    """Public API: get or create a named tracker."""
    return get_registry().get_tracker(name, **kwargs)


def add_handler(handler: HandlerProtocol) -> None:
    """Public API: register a handler with the global registry."""
    get_registry().add_handler(handler)
