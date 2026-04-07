"""Tests for _diagnostics.py — CPU vs IO classification."""

import time

import pytest

from chugchug._diagnostics import DiagnosticSampler
from chugchug._types import DiagnosticKind


class TestDiagnosticSampler:
    def test_cpu_bound(self):
        """CPU-intensive work should classify as CPU_BOUND."""
        sampler = DiagnosticSampler(interval=0.1)
        sampler.start()

        # CPU-bound work
        total = 0
        end = time.monotonic() + 0.5
        while time.monotonic() < end:
            total += sum(range(1000))

        kind = sampler.stop()
        assert kind == DiagnosticKind.CPU_BOUND

    def test_io_bound(self):
        """Sleep-heavy work should classify as IO_BOUND."""
        sampler = DiagnosticSampler(interval=0.1)
        sampler.start()

        # IO-bound work (sleeping)
        time.sleep(0.5)

        kind = sampler.stop()
        assert kind == DiagnosticKind.IO_BOUND

    def test_suggestion_cpu(self):
        msg = DiagnosticSampler.suggestion(DiagnosticKind.CPU_BOUND)
        assert "multiprocessing" in msg.lower()

    def test_suggestion_io(self):
        msg = DiagnosticSampler.suggestion(DiagnosticKind.IO_BOUND)
        assert "asyncio" in msg.lower() or "threading" in msg.lower()

    def test_suggestion_mixed(self):
        msg = DiagnosticSampler.suggestion(DiagnosticKind.MIXED)
        assert "profile" in msg.lower()

    def test_suggestion_unknown(self):
        msg = DiagnosticSampler.suggestion(DiagnosticKind.UNKNOWN)
        assert "could not" in msg.lower()
