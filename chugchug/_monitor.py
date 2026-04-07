"""Resource monitoring — CPU, GPU, memory. Lazy imports for zero overhead."""

from __future__ import annotations

from typing import Any


class ResourceMonitor:
    """Lightweight resource monitoring with lazy imports.

    Zero overhead if no monitoring flags are enabled.
    """

    def __init__(
        self,
        cpu: bool = False,
        memory: bool = False,
        gpu: bool = False,
    ) -> None:
        self._cpu = cpu
        self._memory = memory
        self._gpu = gpu
        self._psutil: Any = None
        self._pynvml: Any = None

        if cpu or memory:
            try:
                import psutil
                self._psutil = psutil
            except ImportError:
                pass

        if gpu:
            try:
                import pynvml
                pynvml.nvmlInit()
                self._pynvml = pynvml
            except (ImportError, Exception):
                pass

    def snapshot(self) -> dict[str, str]:
        """Take a snapshot of current resource usage."""
        stats: dict[str, str] = {}

        if self._psutil:
            if self._cpu:
                stats["cpu"] = f"{self._psutil.cpu_percent():.0f}%"
            if self._memory:
                mem = self._psutil.virtual_memory()
                stats["mem"] = f"{mem.percent:.0f}%"

        if self._pynvml:
            try:
                handle = self._pynvml.nvmlDeviceGetHandleByIndex(0)
                util = self._pynvml.nvmlDeviceGetUtilizationRates(handle)
                mem_info = self._pynvml.nvmlDeviceGetMemoryInfo(handle)
                stats["gpu"] = f"{util.gpu}%"
                stats["vram"] = f"{mem_info.used / 1e9:.1f}G"
            except Exception:
                pass

        return stats

    @property
    def available(self) -> bool:
        return self._psutil is not None or self._pynvml is not None
