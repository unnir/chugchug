"""Auto-detect best handler for the current environment."""

from __future__ import annotations

from typing import TextIO

from ._renderer import JSONHandler, LOGHandler, SilentHandler, TTYHandler
from ._terminal import get_terminal_info
from ._types import HandlerProtocol, OutputMode


def _make_notebook_handler(**kwargs) -> HandlerProtocol:
    """Create a NotebookHandler, falling back to LOGHandler if IPython is missing."""
    try:
        from IPython.display import display  # noqa: F401
        from ._notebook import NotebookHandler
        return NotebookHandler(**kwargs)
    except ImportError:
        return LOGHandler()


def auto_handler(
    file: TextIO | None = None,
    mode: OutputMode | None = None,
    **kwargs,
) -> HandlerProtocol:
    """Create the best handler for the current environment.

    Auto-detection order:
    1. Explicit mode overrides everything
    2. Notebook -> NotebookHandler (HTML/CSS gradient bars)
    3. CI -> LOGHandler or JSONHandler
    4. TTY -> TTYHandler (with capability-aware degradation)
    5. Non-TTY -> LOGHandler
    """
    if mode == OutputMode.SILENT:
        return SilentHandler()
    if mode == OutputMode.JSON:
        return JSONHandler(file=file)
    if mode == OutputMode.LOG:
        return LOGHandler(file=file)

    terminal = get_terminal_info(file)

    if mode is None:
        # Auto-detect
        if terminal.is_notebook:
            return _make_notebook_handler(**kwargs)
        if terminal.is_ci:
            return LOGHandler(file=file, min_interval=5.0)
        if terminal.is_tty:
            return TTYHandler(file=file, **kwargs)
        return LOGHandler(file=file)

    if mode == OutputMode.NOTEBOOK:
        return _make_notebook_handler(**kwargs)

    # mode == TTY (the default) — but if we're actually in a notebook,
    # TTYHandler would output raw ANSI codes that show as garbage.
    # Override to NotebookHandler.
    if terminal.is_notebook:
        return _make_notebook_handler(**kwargs)

    return TTYHandler(file=file, **kwargs)
