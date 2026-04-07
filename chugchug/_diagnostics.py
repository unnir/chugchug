"""\"Why is it slow?\" diagnostics — lightweight CPU/IO/GIL classification.

Samples thread_time vs monotonic to classify workload type.
Prints actionable suggestions on bar close.
Zero overhead when disabled (default off).
"""

from __future__ import annotations

import sys
import threading
import time
from typing import TextIO

from ._types import DiagnosticKind


class DiagnosticSampler:
    """Daemon thread that samples thread_time vs monotonic.

    Classification:
    - CPU-bound: ratio > 0.85 (thread spends most time on CPU)
    - I/O-bound: ratio < 0.3 (thread mostly waiting)
    - Mixed/GIL: in between
    """

    CPU_THRESHOLD = 0.85
    IO_THRESHOLD = 0.3

    def __init__(self, interval: float = 0.5) -> None:
        self._interval = interval
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._samples: list[tuple[float, float]] = []
        self._start_mono: float = 0.0
        self._start_thread: float = 0.0

    def start(self) -> None:
        self._start_mono = time.monotonic()
        self._start_thread = time.thread_time()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            mono = time.monotonic() - self._start_mono
            thread = time.thread_time() - self._start_thread
            self._samples.append((mono, thread))

    def stop(self) -> DiagnosticKind:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

        # Final sample
        mono = time.monotonic() - self._start_mono
        thread = time.thread_time() - self._start_thread

        if mono <= 0:
            return DiagnosticKind.UNKNOWN

        ratio = thread / mono
        return self._classify(ratio)

    def _classify(self, ratio: float) -> DiagnosticKind:
        if ratio > self.CPU_THRESHOLD:
            return DiagnosticKind.CPU_BOUND
        if ratio < self.IO_THRESHOLD:
            return DiagnosticKind.IO_BOUND
        return DiagnosticKind.MIXED

    @staticmethod
    def suggestion(kind: DiagnosticKind) -> str:
        match kind:
            case DiagnosticKind.CPU_BOUND:
                return (
                    "CPU-bound: Consider multiprocessing.Pool or "
                    "ProcessPoolExecutor to utilize multiple cores."
                )
            case DiagnosticKind.IO_BOUND:
                return (
                    "I/O-bound: Consider asyncio, threading, or "
                    "aiohttp/httpx for concurrent I/O operations."
                )
            case DiagnosticKind.MIXED:
                return (
                    "Mixed workload: Profile further with cProfile or py-spy. "
                    "Consider separating CPU and I/O phases."
                )
            case DiagnosticKind.GIL_BOUND:
                return (
                    "GIL-bound: Consider using multiprocessing or "
                    "a GIL-free extension (NumPy, Cython)."
                )
            case _:
                return "Could not classify workload."

    @staticmethod
    def print_diagnostic(kind: DiagnosticKind, file: TextIO | None = None) -> None:
        f = file or sys.stderr
        label = kind.value.replace("_", "-").upper()
        suggestion = DiagnosticSampler.suggestion(kind)
        f.write(f"\n[chugchug diagnostic] {label}: {suggestion}\n")
        f.flush()
