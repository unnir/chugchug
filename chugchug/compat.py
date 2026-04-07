"""tqdm drop-in compatibility layer.

Accepts all common tqdm kwargs and maps them to ChugConfig.
Usage:
    from chugchug.compat import tqdm, trange
    for x in tqdm(range(100)):
        pass
"""

from __future__ import annotations

import sys
from typing import Any, Iterable, TypeVar

from ._bar import Chug
from ._types import OutputMode

T = TypeVar("T")


class tqdm(Chug[T]):
    """tqdm-compatible progress bar wrapper.

    Accepts common tqdm kwargs and maps them to chugchug's API.
    """

    def __init__(
        self,
        iterable: Iterable[T] | None = None,
        desc: str | None = None,
        total: int | None = None,
        leave: bool = True,
        file: Any = None,
        ncols: int | None = None,
        mininterval: float = 0.1,
        maxinterval: float = 10.0,
        miniters: int | None = None,
        ascii: bool | str | None = None,
        disable: bool = False,
        unit: str = "it",
        unit_scale: bool | int | float = False,
        dynamic_ncols: bool = False,
        smoothing: float = 0.3,
        bar_format: str | None = None,
        initial: int = 0,
        position: int | None = None,
        postfix: dict | None = None,
        unit_divisor: int = 1000,
        colour: str | None = None,
        delay: float = 0,
        gui: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            iterable,
            desc=desc or "",
            total=total,
            width=ncols,
            ascii=bool(ascii) if ascii else False,
            file=file,
            min_interval=mininterval,
            min_iters=miniters or 1,
            leave=leave,
            position=position,
            unit=unit,
            unit_scale=bool(unit_scale),
            colour=colour,
            disable=disable,
        )

        if initial > 0:
            self._tracker._n = initial
            self._last_print_n = initial

        if postfix:
            self.set_postfix(**postfix)

    @staticmethod
    def write(s: str, file: Any = None, end: str = "\n", nolock: bool = False) -> None:
        """Print a message, clearing the progress bar first."""
        f = file or sys.stderr
        f.write("\r\033[K")
        f.write(s + end)
        f.flush()

    @staticmethod
    def pandas() -> None:
        """Stub for tqdm.pandas() — not yet supported."""
        pass


def trange(*args: int, **kwargs: Any) -> tqdm[int]:
    """tqdm-compatible trange()."""
    return tqdm(range(*args), **kwargs)
