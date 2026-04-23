"""ChugConfig dataclass — fully typed configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TextIO

from ._types import OutputMode


@dataclass
class ChugConfig:
    """Fully typed configuration for a progress bar."""

    desc: str = ""
    total: int | None = None
    width: int | None = None
    gradient: str = "ocean"
    ascii: bool = False
    output: OutputMode | None = None
    # None instead of sys.stderr for spawn safety (resolved at use time)
    file: TextIO | None = None

    # Update control
    min_interval: float = 0.05
    min_iters: int = 1

    # ETA
    eta_strategy: str = "adaptive"
    eta_window: int = 50

    # Resource monitoring
    monitor_cpu: bool = False
    monitor_memory: bool = False
    monitor_gpu: bool = False

    # Persistence
    persist_path: Path | None = None

    # Callbacks
    callbacks: list[Callable[..., Any]] = field(default_factory=list)

    # ML Training
    show_metrics: bool = True

    # Display
    leave: bool = True
    position: int | None = None
    unit: str = "it"
    unit_scale: bool = False
    colour: str | None = None

    # Logging integration
    log_every: int | None = None

    # Diagnostics
    diagnostics: bool = False

    # Disable
    disable: bool = False
