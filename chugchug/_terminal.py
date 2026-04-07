"""Terminal capability detection — cached per file object."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import TextIO


class ColorDepth(Enum):
    NONE = 0
    BASIC = 16
    EXTENDED = 256
    TRUECOLOR = 16_777_216


@dataclass(frozen=True, slots=True)
class TerminalInfo:
    """Detected terminal capabilities."""
    is_tty: bool = False
    width: int = 80
    color_depth: ColorDepth = ColorDepth.NONE
    unicode_support: bool = True
    is_notebook: bool = False
    is_ci: bool = False
    ci_system: str | None = None


_CI_ENV_VARS = {
    "GITHUB_ACTIONS": "github_actions",
    "GITLAB_CI": "gitlab_ci",
    "CIRCLECI": "circleci",
    "TRAVIS": "travis",
    "JENKINS_URL": "jenkins",
    "BUILDKITE": "buildkite",
    "TF_BUILD": "azure_devops",
}


def _detect_notebook() -> bool:
    try:
        from IPython import get_ipython
        shell = get_ipython()
        if shell is None:
            return False
        return shell.__class__.__name__ == "ZMQInteractiveShell"
    except (ImportError, NameError):
        return False


def _detect_color_depth(file: TextIO | None) -> ColorDepth:
    if os.environ.get("NO_COLOR"):
        return ColorDepth.NONE
    if os.environ.get("FORCE_COLOR"):
        colorterm = os.environ.get("COLORTERM", "")
        if colorterm in ("truecolor", "24bit"):
            return ColorDepth.TRUECOLOR
        return ColorDepth.EXTENDED

    f = file or sys.stderr
    if not (hasattr(f, "isatty") and f.isatty()):
        return ColorDepth.NONE

    colorterm = os.environ.get("COLORTERM", "")
    if colorterm in ("truecolor", "24bit"):
        return ColorDepth.TRUECOLOR

    term = os.environ.get("TERM", "")
    if "256color" in term:
        return ColorDepth.EXTENDED
    if term in ("dumb", ""):
        return ColorDepth.NONE

    return ColorDepth.BASIC


def _detect_ci() -> tuple[bool, str | None]:
    if os.environ.get("CI"):
        for env_var, name in _CI_ENV_VARS.items():
            if os.environ.get(env_var):
                return True, name
        return True, "unknown"
    for env_var, name in _CI_ENV_VARS.items():
        if os.environ.get(env_var):
            return True, name
    return False, None


def detect_terminal(file: TextIO | None = None) -> TerminalInfo:
    """Detect terminal capabilities for the given file object."""
    f = file or sys.stderr
    is_tty = hasattr(f, "isatty") and f.isatty()
    is_notebook = _detect_notebook()
    is_ci, ci_system = _detect_ci()

    try:
        width = shutil.get_terminal_size().columns
    except Exception:
        width = 80

    color_depth = _detect_color_depth(file)

    unicode_support = True
    if os.environ.get("TERM") == "dumb":
        unicode_support = False

    return TerminalInfo(
        is_tty=is_tty,
        width=width,
        color_depth=color_depth,
        unicode_support=unicode_support,
        is_notebook=is_notebook,
        is_ci=is_ci,
        ci_system=ci_system,
    )


@lru_cache(maxsize=8)
def _cached_detect(file_id: int) -> TerminalInfo:
    """Cache by file id — used internally."""
    return detect_terminal()


def get_terminal_info(file: TextIO | None = None) -> TerminalInfo:
    """Get cached terminal info for a file object."""
    if file is None:
        file = sys.stderr
    return detect_terminal(file)
