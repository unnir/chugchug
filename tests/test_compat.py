"""Tests for compat.py — tqdm API compatibility."""

import io
import time

import pytest

from chugchug.compat import tqdm, trange


class TestTqdmCompat:
    def test_basic_iteration(self):
        items = list(tqdm(range(10), disable=True))
        assert items == list(range(10))

    def test_trange(self):
        items = list(trange(5, disable=True))
        assert items == list(range(5))

    def test_with_desc(self):
        items = list(tqdm(range(5), desc="test", disable=True))
        assert items == list(range(5))

    def test_manual_update(self):
        bar = tqdm(total=10, disable=True)
        for _ in range(10):
            bar.update(1)
        assert bar.n == 10
        bar.close()

    def test_set_postfix(self):
        bar = tqdm(total=10, disable=True)
        bar.set_postfix(loss=0.5, acc=0.9)
        bar.update()
        bar.close()

    def test_write(self):
        buf = io.StringIO()
        tqdm.write("hello", file=buf)
        assert "hello" in buf.getvalue()

    def test_leave_false(self):
        buf = io.StringIO()
        bar = tqdm(range(5), file=buf, leave=False, disable=True)
        list(bar)

    def test_initial(self):
        bar = tqdm(total=100, initial=50, disable=True)
        assert bar.n == 50
        bar.close()

    def test_context_manager(self):
        with tqdm(total=10, disable=True) as bar:
            for _ in range(10):
                bar.update()
            assert bar.n == 10

    def test_unit_and_unit_scale(self):
        items = list(tqdm(range(5), unit="img", unit_scale=True, disable=True))
        assert items == list(range(5))

    def test_pandas_stub(self):
        # Should not raise
        tqdm.pandas()
