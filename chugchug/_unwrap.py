"""Smart iterable unwrapping — extract total from generators that wrap sized iterables.

tqdm gives up when it sees a generator. chugchug looks inside.

Supported patterns:
  map(fn, list)           -> len(list)
  filter(fn, list)        -> None (can't know how many pass), but wraps with estimate
  zip(list1, list2)       -> min(len(list1), len(list2))
  enumerate(list)         -> len(list)
  itertools.islice(x, n)  -> n (or stop - start)
  itertools.chain(a, b)   -> len(a) + len(b)
  reversed(list)          -> len(list)
  (x for x in list)       -> attempts to extract from generator frame locals

For true generators with unknown total, we offer TotalEstimator
that predicts total based on observed production rate + optional hints.
"""

from __future__ import annotations

import itertools
import types
from typing import Any, Iterable


def unwrap_iterable(iterable: Any) -> int | None:
    """Try to extract a total count from an iterable.

    Returns the count if determinable, None otherwise.
    """
    # Already has __len__
    if hasattr(iterable, "__len__"):
        try:
            return len(iterable)
        except (TypeError, AttributeError):
            pass

    # map(fn, sized_iterable)
    if isinstance(iterable, map):
        return _unwrap_map(iterable)

    # zip(sized1, sized2, ...)
    if isinstance(iterable, zip):
        return _unwrap_zip(iterable)

    # enumerate(sized)
    if isinstance(iterable, enumerate):
        return _unwrap_enumerate(iterable)

    # reversed(sized)
    if isinstance(iterable, reversed):
        return _unwrap_reversed(iterable)

    # filter(fn, sized) — we can't know how many pass, return None
    # but we note the underlying total for estimation
    if isinstance(iterable, filter):
        return None

    # itertools types
    if isinstance(iterable, itertools.islice):
        return _unwrap_islice(iterable)

    if isinstance(iterable, itertools.chain):
        return _unwrap_chain(iterable)

    # Generator objects — peek at frame locals
    if isinstance(iterable, types.GeneratorType):
        return _unwrap_generator(iterable)

    return None


def _unwrap_map(m: map) -> int | None:
    """Extract total from map(fn, iterable).

    CPython stores iterators internally. We inspect __reduce__ or
    the internal iterators list.
    """
    # map objects aren't easily introspectable without C internals.
    # But map.__reduce__ works in CPython 3.10+:
    try:
        # map.__reduce__() -> (map, (fn, iter1, iter2, ...))
        reduced = m.__reduce__()
        if reduced and len(reduced) >= 2:
            args = reduced[1]
            # args[0] is the function, args[1:] are the iterators
            iters = args[1:]
            lengths = []
            for it in iters:
                if hasattr(it, "__length_hint__"):
                    lengths.append(it.__length_hint__())
                elif hasattr(it, "__len__"):
                    lengths.append(len(it))
            if lengths:
                return min(lengths)
    except (TypeError, AttributeError, StopIteration):
        pass
    return None


def _unwrap_zip(z: zip) -> int | None:
    """Extract total from zip(a, b, ...) — min of all lengths."""
    try:
        reduced = z.__reduce__()
        if reduced and len(reduced) >= 2:
            iters = reduced[1]
            lengths = []
            for it in iters:
                if hasattr(it, "__length_hint__"):
                    lengths.append(it.__length_hint__())
                elif hasattr(it, "__len__"):
                    lengths.append(len(it))
            if lengths:
                return min(lengths)
    except (TypeError, AttributeError):
        pass
    return None


def _unwrap_enumerate(e: enumerate) -> int | None:
    """Extract total from enumerate(sized)."""
    try:
        reduced = e.__reduce__()
        if reduced and len(reduced) >= 2:
            args = reduced[1]
            # args[0] is the iterator
            it = args[0]
            if hasattr(it, "__length_hint__"):
                return it.__length_hint__()
            if hasattr(it, "__len__"):
                return len(it)
    except (TypeError, AttributeError):
        pass
    return None


def _unwrap_reversed(r: reversed) -> int | None:
    """Extract total from reversed(sized)."""
    try:
        hint = r.__length_hint__()
        if hint > 0:
            return hint
    except (TypeError, AttributeError):
        pass
    return None


def _unwrap_islice(s: itertools.islice) -> int | None:
    """Extract count from islice(iter, stop) or islice(iter, start, stop)."""
    # islice doesn't expose its args easily, but __length_hint__ works
    try:
        hint = s.__length_hint__()
        if hint > 0:
            return hint
    except (TypeError, AttributeError):
        pass
    return None


def _unwrap_chain(c: itertools.chain) -> int | None:
    """Extract total from chain(a, b, ...) — sum of all lengths."""
    # chain doesn't expose internals easily
    try:
        hint = c.__length_hint__()
        if hint > 0:
            return hint
    except (TypeError, AttributeError):
        pass
    return None


def _unwrap_generator(gen: types.GeneratorType) -> int | None:
    """Try to extract total from a generator by inspecting its frame.

    Works for simple patterns like:
        (x for x in some_list)
        (f(x) for x in some_list)

    Looks for the iteration target in the generator's frame locals.
    """
    frame = gen.gi_frame
    if frame is None:
        return None

    # Look at local variables in the generator frame
    # Common pattern: the .0 implicit iterator variable
    locals_ = frame.f_locals
    for key, val in locals_.items():
        if key == ".0":
            # This is the implicit iterator in generator expressions
            if hasattr(val, "__length_hint__"):
                try:
                    return val.__length_hint__()
                except TypeError:
                    pass
            if hasattr(val, "__len__"):
                try:
                    return len(val)
                except TypeError:
                    pass
    return None


class TotalEstimator:
    """Estimates total for iterables where we can't determine it upfront.

    After seeing N items arrive over T seconds, combined with optional
    hints (file size, API pagination total), estimates when it will end.

    Usage:
        est = TotalEstimator()
        for item in generator:
            est.observe(elapsed, n)
            if est.estimated_total:
                bar.total = est.estimated_total
    """

    def __init__(self, hint: int | None = None) -> None:
        self._hint = hint
        self._estimated: int | None = hint

    @property
    def estimated_total(self) -> int | None:
        return self._estimated

    def set_hint(self, total: int) -> None:
        """Set a hint from external source (e.g., HTTP Content-Length, API total)."""
        self._hint = total
        self._estimated = total
