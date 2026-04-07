"""Shared types, protocols, and enums — zero internal imports."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


# ─── Enums ────────────────────────────────────────────────────────────────────

class OutputMode(Enum):
    TTY = "tty"
    LOG = "log"
    JSON = "json"
    SILENT = "silent"
    NOTEBOOK = "notebook"


class TrackerState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class DiagnosticKind(Enum):
    CPU_BOUND = "cpu_bound"
    IO_BOUND = "io_bound"
    MIXED = "mixed"
    GIL_BOUND = "gil_bound"
    UNKNOWN = "unknown"


# ─── ProgressEvent ────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """Immutable, picklable progress event — the fundamental unit of progress."""
    tracker_name: str
    n: int
    total: int | None = None
    elapsed: float = 0.0
    timestamp: float = field(default_factory=time.monotonic)
    desc: str = ""
    metrics: tuple[tuple[str, str], ...] = ()
    state: TrackerState = TrackerState.RUNNING
    parent: str | None = None

    @property
    def fraction(self) -> float | None:
        if self.total is not None and self.total > 0:
            return min(self.n / self.total, 1.0)
        return None

    @property
    def metrics_dict(self) -> dict[str, str]:
        return dict(self.metrics)


# ─── Protocols ────────────────────────────────────────────────────────────────

@runtime_checkable
class TrackerProtocol(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def n(self) -> int: ...
    @property
    def total(self) -> int | None: ...
    def update(self, n: int = 1) -> None: ...
    def set_description(self, desc: str) -> None: ...
    def set_metrics(self, **kwargs: str) -> None: ...
    def complete(self) -> None: ...
    def close(self) -> None: ...


@runtime_checkable
class HandlerProtocol(Protocol):
    def on_event(self, event: ProgressEvent) -> None: ...
    def on_close(self, tracker_name: str) -> None: ...


@runtime_checkable
class ETAProtocol(Protocol):
    def update(self, n: int, timestamp: float | None = None) -> None: ...
    def eta(self, current: int, total: int) -> float | None: ...
    @property
    def rate(self) -> float | None: ...
