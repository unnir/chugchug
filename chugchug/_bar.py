"""Bar — the main user-facing class. Composes Tracker + Handler + Config."""

from __future__ import annotations

import sys
import time
from typing import Any, AsyncIterator, Generic, Iterable, Iterator, TypeVar

from ._config import ChugConfig
from ._types import HandlerProtocol, OutputMode, ProgressEvent, TrackerState
from ._tracker import Registry, Tracker, get_registry
from .auto import auto_handler

T = TypeVar("T")


class Chug(Generic[T]):
    """A modern progress bar. Composes Tracker + Handler (no inheritance).

    Usage:
        # Iterate
        for item in Chug(range(100), desc="Working"):
            process(item)

        # Manual
        with Chug(total=100, desc="Working") as bar:
            for i in range(100):
                do_work()
                bar.update()

        # Metrics
        bar = Chug(total=50, desc="Training", gradient="fire")
        for step in range(50):
            loss = train()
            bar.set_metrics(loss=f"{loss:.4f}")
            bar.update()
        bar.close()
    """

    def __init__(
        self,
        iterable: Iterable[T] | None = None,
        *,
        desc: str = "",
        total: int | None = None,
        width: int | None = None,
        gradient: str = "ocean",
        ascii: bool = False,
        output: OutputMode | str | None = None,
        file: Any = None,
        min_interval: float = 0.05,
        min_iters: int = 1,
        eta_strategy: str = "adaptive",
        eta_window: int = 50,
        monitor_cpu: bool = False,
        monitor_memory: bool = False,
        monitor_gpu: bool = False,
        persist_path: Any = None,
        callbacks: list | None = None,
        show_metrics: bool = True,
        leave: bool = True,
        position: int | None = None,
        unit: str = "it",
        unit_scale: bool = False,
        colour: str | None = None,
        log_every: int | None = None,
        diagnostics: bool = False,
        disable: bool = False,
        config: ChugConfig | None = None,
    ) -> None:
        if config is not None:
            c = config
        else:
            if isinstance(output, str):
                output = OutputMode(output)
            from pathlib import Path
            c = ChugConfig(
                desc=desc, total=total, width=width, gradient=gradient,
                ascii=ascii, output=output, file=file,
                min_interval=min_interval, min_iters=min_iters,
                eta_strategy=eta_strategy, eta_window=eta_window,
                monitor_cpu=monitor_cpu, monitor_memory=monitor_memory,
                monitor_gpu=monitor_gpu,
                persist_path=Path(persist_path) if persist_path else None,
                callbacks=callbacks or [],
                show_metrics=show_metrics, leave=leave, position=position,
                unit=unit, unit_scale=unit_scale, colour=colour,
                log_every=log_every, diagnostics=diagnostics, disable=disable,
            )

        self._config = c
        self._iterable = iterable
        self._closed = False

        # Resolve file
        self._file = c.file or sys.stderr

        # Determine total — smart unwrapping for generators
        if c.total is not None:
            self._total = c.total
        elif iterable is not None:
            try:
                self._total = len(iterable)  # type: ignore
            except (TypeError, AttributeError):
                # Smart unwrap: extract total from map/zip/enumerate/etc.
                from ._unwrap import unwrap_iterable
                self._total = unwrap_iterable(iterable)
        else:
            self._total = None

        # Disable suppresses all tracking. Silent mode still dispatches to
        # non-rendering handlers such as persistence.
        self._disable = c.disable

        # Create handler (auto-detect if needed)
        self._handler: HandlerProtocol = self._create_handler()

        self._system_metrics: dict[str, str] = {}
        self._resource_monitor: Any = None
        self._diagnostic_sampler: Any = None
        self._persistence: Any = None

        if c.monitor_cpu or c.monitor_memory or c.monitor_gpu:
            from ._monitor import ResourceMonitor
            self._resource_monitor = ResourceMonitor(
                cpu=c.monitor_cpu,
                memory=c.monitor_memory,
                gpu=c.monitor_gpu,
            )

        # Create a private registry + tracker for this bar
        self._registry = Registry()
        self._registry.add_handler(self._handler)
        if c.persist_path is not None:
            from ._persistence import PersistenceHandler
            self._persistence = PersistenceHandler(c.persist_path)
            self._registry.add_handler(self._persistence)
        self._tracker = Tracker(
            name=c.desc or "chug",
            total=self._total,
            desc=c.desc,
            registry=self._registry,
        )

        if c.diagnostics and c.output != OutputMode.SILENT and not self._disable:
            from ._diagnostics import DiagnosticSampler
            self._diagnostic_sampler = DiagnosticSampler()
            self._diagnostic_sampler.start()

        # State for throttling
        self._last_print_n = 0
        self._last_print_time = 0.0

    def _create_handler(self) -> HandlerProtocol:
        c = self._config
        if self._disable:
            from ._renderer import SilentHandler
            return SilentHandler()

        return auto_handler(
            file=self._file,
            mode=c.output,
            min_interval=c.min_interval,
            gradient=c.colour or c.gradient,
            ascii_mode=c.ascii,
            bar_width=c.width,
            unit=c.unit,
            unit_scale=c.unit_scale,
            show_metrics=c.show_metrics,
            eta_strategy=c.eta_strategy,
            eta_window=c.eta_window,
        )

    def _update_system_metrics(self) -> None:
        if self._resource_monitor is None:
            return
        self._system_metrics = self._resource_monitor.snapshot()

    def _merged_metrics(self) -> dict[str, str]:
        return {**self._system_metrics, **self._tracker._metrics}

    def _make_event(self) -> ProgressEvent:
        self._update_system_metrics()
        return ProgressEvent(
            tracker_name=self._tracker.name,
            n=self._tracker.n,
            total=self._tracker.total,
            elapsed=time.monotonic() - self._tracker._start_time,
            desc=self._tracker._desc,
            metrics=tuple(self._merged_metrics().items()),
            state=self._tracker.state,
        )

    # ─── Iteration Protocol ──────────────────────────────────────────────

    def __iter__(self) -> Iterator[T]:
        if self._iterable is None:
            raise TypeError("Chug has no iterable to iterate over")
        return self._iter_gen()

    async def __aiter__(self) -> AsyncIterator[T]:
        if self._iterable is None:
            raise TypeError("Chug has no iterable to iterate over")
        try:
            if hasattr(self._iterable, "__aiter__"):
                async for item in self._iterable:  # type: ignore
                    yield item
                    self.update(1)
            else:
                for item in self._iterable:
                    yield item
                    self.update(1)
        except Exception:
            self._print_crash_context()
            raise
        self.close()

    def __enter__(self) -> Chug[T]:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self._print_crash_context(exc_val)
        self.close()

    def __len__(self) -> int:
        if self.total is not None:
            return self.total
        raise TypeError("Chug has no length")

    def _iter_gen(self) -> Iterator[T]:
        """Internal generator for iteration."""
        for item in self._iterable:  # type: ignore
            yield item
            self.update(1)
        self.close()

    # ─── Core API ────────────────────────────────────────────────────────

    def update(self, n: int = 1) -> None:
        """Advance the progress bar by n steps."""
        self._tracker._n += n

        if self._disable or self._closed:
            return
        now = time.monotonic()
        dn = self._tracker._n - self._last_print_n
        dt = now - self._last_print_time

        if dt >= self._config.min_interval and dn >= self._config.min_iters:
            self._tracker._state = TrackerState.RUNNING
            event = self._make_event()
            self._registry.dispatch(event)
            self._last_print_time = now
            self._last_print_n = self._tracker._n

            # Callbacks
            for cb in self._config.callbacks:
                cb(self.format_dict)

    def set_metrics(self, **kwargs: str) -> None:
        """Set custom metrics to display (e.g., loss, accuracy)."""
        self._tracker.set_metrics(**kwargs)

    def set_description(self, desc: str) -> None:
        self._config.desc = desc
        self._tracker.set_description(desc)

    def set_postfix(self, **kwargs: Any) -> None:
        """tqdm compatibility — maps to set_metrics."""
        self._tracker.set_metrics(**{k: str(v) for k, v in kwargs.items()})

    def reset(self, total: int | None = None) -> None:
        """Reset progress bar for reuse."""
        self._tracker.reset(total)
        if total is not None:
            self._total = total
            self._config.total = total
        self._system_metrics.clear()
        self._last_print_n = 0
        self._last_print_time = 0.0

    def complete(self) -> None:
        """Mark progress as complete (useful for early exits)."""
        if self.total is not None:
            self._tracker._n = self.total
        self._tracker._state = TrackerState.COMPLETED
        event = self._make_event()
        self._registry.dispatch(event)
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if not self._disable:
            self._tracker._state = TrackerState.COMPLETED
            event = self._make_event()
            self._registry.dispatch(event)
            self._registry.close_tracker(self._tracker.name)
            if not self._config.leave:
                self._file.write("\r\033[K")
                self._file.flush()
            self._print_diagnostic()

    # ─── Properties ──────────────────────────────────────────────────────

    @property
    def n(self) -> int:
        return self._tracker._n

    @n.setter
    def n(self, value: int) -> None:
        self._tracker._n = value

    @property
    def total(self) -> int | None:
        return self._tracker.total

    @property
    def format_dict(self) -> dict[str, Any]:
        elapsed = time.monotonic() - self._tracker._start_time
        total = self.total
        return {
            "n": self._tracker._n,
            "total": total,
            "elapsed": round(elapsed, 3),
            "percentage": round(100 * self._tracker._n / total, 2) if total else None,
            "desc": self._tracker._desc,
            "metrics": self._merged_metrics(),
            "unit": self._config.unit,
        }

    # ─── Crash Context ───────────────────────────────────────────────

    def _print_diagnostic(self) -> None:
        if self._diagnostic_sampler is None:
            return
        sampler = self._diagnostic_sampler
        self._diagnostic_sampler = None
        from ._diagnostics import DiagnosticSampler
        kind = sampler.stop()
        DiagnosticSampler.print_diagnostic(kind, file=self._file)

    def _print_crash_context(self, exc: Any = None) -> None:
        """Print rich context when an exception occurs inside the loop."""
        if self._disable or self._config.output == OutputMode.SILENT:
            return
        from ._format import format_time
        f = self._file
        elapsed = time.monotonic() - self._tracker._start_time
        n = self._tracker._n
        total = self.total

        # Build context line
        parts = [f"\n[chugchug] Failed at iteration {n:,}"]
        if total:
            pct = 100 * n / total
            parts[0] += f"/{total:,} ({pct:.1f}%)"
        parts.append(f"after {format_time(elapsed)}")

        metrics = self._tracker._metrics
        if metrics:
            metrics_str = " ".join(f"{k}={v}" for k, v in metrics.items())
            parts.append(f"with {metrics_str}")

        if exc is not None:
            parts.append(f"-- {type(exc).__name__}: {exc}")

        f.write(" ".join(parts) + "\n")
        f.flush()


def chug(
    iterable: Iterable[T] | None = None,
    *,
    desc: str = "",
    total: int | None = None,
    disable: bool = False,
    **kwargs: Any,
) -> Chug[T]:
    """Convenience function — like tqdm()."""
    return Chug(iterable, desc=desc, total=total, disable=disable, **kwargs)
