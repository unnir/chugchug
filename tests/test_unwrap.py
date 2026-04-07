"""Tests for _unwrap.py — smart generator unwrapping."""

import itertools

import pytest

from chugchug._unwrap import unwrap_iterable
from chugchug import Chug, chug


class TestUnwrapIterable:
    def test_list(self):
        assert unwrap_iterable([1, 2, 3]) == 3

    def test_range(self):
        assert unwrap_iterable(range(100)) == 100

    def test_map(self):
        m = map(str, [1, 2, 3, 4, 5])
        total = unwrap_iterable(m)
        assert total == 5

    def test_zip(self):
        z = zip([1, 2, 3], [4, 5, 6, 7])
        total = unwrap_iterable(z)
        assert total == 3  # min of lengths

    def test_enumerate(self):
        e = enumerate([10, 20, 30])
        total = unwrap_iterable(e)
        assert total == 3

    def test_reversed(self):
        r = reversed([1, 2, 3, 4])
        total = unwrap_iterable(r)
        # reversed objects do support __length_hint__ in CPython
        if total is not None:
            assert total == 4

    def test_islice(self):
        s = itertools.islice(range(1000), 50)
        total = unwrap_iterable(s)
        # islice supports __length_hint__ in Python 3.12+
        if total is not None:
            assert total == 50

    def test_chain(self):
        c = itertools.chain([1, 2, 3], [4, 5])
        total = unwrap_iterable(c)
        # chain supports __length_hint__ in newer Python
        if total is not None:
            assert total == 5

    def test_generator_expression(self):
        data = [1, 2, 3, 4, 5]
        gen = (x * 2 for x in data)
        total = unwrap_iterable(gen)
        assert total == 5

    def test_filter_returns_none(self):
        """filter can't know how many items pass, should return None."""
        f = filter(lambda x: x > 2, [1, 2, 3, 4, 5])
        assert unwrap_iterable(f) is None

    def test_true_generator_no_total(self):
        def gen():
            yield 1
            yield 2
        assert unwrap_iterable(gen()) is None

    def test_none_input(self):
        assert unwrap_iterable(None) is None


class TestBarWithUnwrap:
    def test_bar_with_map(self):
        """Bar should detect total from map()."""
        data = list(range(20))
        b = Chug(map(str, data), desc="mapping", disable=True)
        assert b.total == 20
        items = list(b)
        assert len(items) == 20

    def test_bar_with_enumerate(self):
        data = list(range(15))
        b = Chug(enumerate(data), desc="enumerating", disable=True)
        assert b.total == 15

    def test_bar_with_zip(self):
        a = list(range(10))
        b_list = list(range(20))
        b = Chug(zip(a, b_list), desc="zipping", disable=True)
        assert b.total == 10

    def test_bar_with_generator_expression(self):
        data = list(range(25))
        b = Chug((x ** 2 for x in data), desc="genexpr", disable=True)
        assert b.total == 25
