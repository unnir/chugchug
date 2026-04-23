"""chugchug — Next-generation progress bars for Python.

Usage:
    from chugchug import chug, Chug, ChugConfig

    # Simple iteration
    for item in chug(range(100), desc="Working"):
        process(item)

    # Protocol-based
    from chugchug import tracker, add_handler
    t = tracker("download", total=1000)
    t.update(100)

    # tqdm drop-in
    from chugchug.compat import tqdm, trange
"""

__version__ = "0.1.3"
__author__ = "Tabularis.AI"

from ._bar import Chug, chug
from ._config import ChugConfig
from ._types import (
    DiagnosticKind,
    HandlerProtocol,
    OutputMode,
    ProgressEvent,
    TrackerProtocol,
    TrackerState,
)
from ._tracker import Registry, Tracker, add_handler, get_registry, tracker
from ._renderer import JSONHandler, LOGHandler, SilentHandler, TTYHandler
from ._notebook import NotebookHandler
from ._gradient import GRADIENTS, register_gradient, register_multi_gradient
from ._eta import AdaptiveETA, DoubleExponentialETA, WeightedRegressionETA, create_eta
from ._format import format_bytes, format_count, format_rate, format_time

__all__ = [
    # Main API
    "chug",
    "Chug",
    "ChugConfig",
    # Protocol/types
    "ProgressEvent",
    "TrackerProtocol",
    "HandlerProtocol",
    "OutputMode",
    "TrackerState",
    "DiagnosticKind",
    # Tracker/Registry
    "tracker",
    "add_handler",
    "get_registry",
    "Tracker",
    "Registry",
    # Handlers
    "TTYHandler",
    "JSONHandler",
    "LOGHandler",
    "SilentHandler",
    "NotebookHandler",
    # Gradient
    "GRADIENTS",
    "register_gradient",
    "register_multi_gradient",
    # ETA
    "WeightedRegressionETA",
    "DoubleExponentialETA",
    "AdaptiveETA",
    "create_eta",
    # Format
    "format_time",
    "format_rate",
    "format_count",
    "format_bytes",
]
