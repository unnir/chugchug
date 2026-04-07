"""Crash recovery + time-series JSONL persistence."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any

from ._types import HandlerProtocol, ProgressEvent, TrackerState


class PersistenceHandler:
    """Saves progress state atomically for crash recovery.

    Writes a JSON file that can be loaded on restart to resume progress.
    Uses atomic write (write to temp, rename) to prevent corruption.
    """

    def __init__(
        self,
        path: str | Path,
        save_every_n: int = 100,
    ) -> None:
        self._path = Path(path)
        self._save_every_n = save_every_n
        self._states: dict[str, dict[str, Any]] = {}
        self._counters: dict[str, int] = {}

    def on_event(self, event: ProgressEvent) -> None:
        name = event.tracker_name
        self._counters[name] = self._counters.get(name, 0) + 1

        self._states[name] = {
            "n": event.n,
            "total": event.total,
            "elapsed": event.elapsed,
            "metrics": event.metrics_dict,
            "state": event.state.value,
        }

        if self._counters[name] % self._save_every_n == 0:
            self._save()

    def on_close(self, tracker_name: str) -> None:
        self._save()

    def _save(self) -> None:
        data = {
            "timestamp": time.time(),
            "trackers": self._states,
        }
        # Atomic write
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.rename(self._path)

    def load(self) -> dict[str, dict[str, Any]]:
        """Load saved state. Returns tracker states dict."""
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text())
            return data.get("trackers", {})
        except (json.JSONDecodeError, KeyError):
            return {}


class TimeSeriesHandler:
    """Append-only JSONL time series for analysis and replay."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def on_event(self, event: ProgressEvent) -> None:
        record = {
            "t": time.time(),
            "tracker": event.tracker_name,
            "n": event.n,
            "total": event.total,
            "elapsed": round(event.elapsed, 3),
            "state": event.state.value,
            "metrics": event.metrics_dict,
        }
        with open(self._path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def on_close(self, tracker_name: str) -> None:
        pass

    def read(self) -> list[dict[str, Any]]:
        """Read all records."""
        if not self._path.exists():
            return []
        records = []
        for line in self._path.read_text().strip().split("\n"):
            if line:
                records.append(json.loads(line))
        return records
