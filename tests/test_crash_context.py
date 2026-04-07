"""Tests for exception context on crash.

Crash context works via the context manager pattern:
    with Chug(range(100)) as b:
        for item in b:
            ...  # exception here prints rich context

This is because Python doesn't expose the caller's exception to generators,
so bare `for item in Chug(...)` can't detect crashes. The `with` pattern
uses __exit__ which reliably receives the exception.
"""

import io

import pytest

from chugchug import Chug


class TestCrashContext:
    def test_context_manager_crash(self):
        """Exception in context manager prints context."""
        buf = io.StringIO()

        with pytest.raises(ValueError, match="boom"):
            with Chug(range(100), desc="crash test", file=buf) as b:
                for i in b:
                    if i == 42:
                        raise ValueError("boom")

        output = buf.getvalue()
        assert "Failed at iteration" in output
        assert "42" in output or "43" in output  # depends on update timing
        assert "ValueError" in output
        assert "boom" in output

    def test_context_manager_with_total(self):
        """Crash context shows percentage when total is known."""
        buf = io.StringIO()

        with pytest.raises(RuntimeError):
            with Chug(range(200), desc="pct crash", file=buf) as b:
                for i in b:
                    if i == 100:
                        raise RuntimeError("half")

        output = buf.getvalue()
        assert "Failed at iteration" in output
        assert "200" in output  # total shown
        assert "RuntimeError" in output

    def test_manual_bar_crash(self):
        """Manual update with context manager also gets crash context."""
        buf = io.StringIO()

        with pytest.raises(RuntimeError):
            with Chug(total=100, desc="manual crash", file=buf) as b:
                for i in range(100):
                    b.update()
                    if i == 10:
                        raise RuntimeError("manual error")

        output = buf.getvalue()
        assert "Failed at iteration" in output
        assert "RuntimeError" in output

    def test_crash_with_metrics(self):
        """Metrics are included in crash context."""
        buf = io.StringIO()

        with pytest.raises(ValueError):
            with Chug(total=50, desc="metrics crash", file=buf) as b:
                for i in range(50):
                    b.set_metrics(step=str(i))
                    b.update()
                    if i == 5:
                        raise ValueError("oops")

        output = buf.getvalue()
        assert "Failed at iteration" in output
        # Metrics may or may not be in crash line depending on throttle
        assert "ValueError" in output

    def test_disabled_bar_no_crash_output(self):
        """Disabled bars don't print crash context."""
        buf = io.StringIO()

        with pytest.raises(ValueError):
            with Chug(range(100), file=buf, disable=True) as b:
                for i in b:
                    if i == 10:
                        raise ValueError("silent")

        output = buf.getvalue()
        assert "Failed at iteration" not in output

    def test_normal_completion_no_crash(self):
        """Normal completion should NOT print crash context."""
        buf = io.StringIO()
        items = list(Chug(range(5), desc="normal", file=buf))
        assert items == [0, 1, 2, 3, 4]
        output = buf.getvalue()
        assert "Failed" not in output

    def test_normal_context_manager_no_crash(self):
        """Normal context manager completion doesn't print crash context."""
        buf = io.StringIO()
        with Chug(total=5, desc="normal ctx", file=buf) as b:
            for _ in range(5):
                b.update()
        output = buf.getvalue()
        assert "Failed" not in output
