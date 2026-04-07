"""Extra handlers — webhooks, file logging, Python logging integration."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from ._format import format_time
from ._types import HandlerProtocol, ProgressEvent


class WebhookHandler:
    """POST progress events to a webhook URL with async batching.

    Events are batched and sent periodically to avoid overwhelming the endpoint.
    """

    def __init__(
        self,
        url: str,
        batch_interval: float = 5.0,
        max_batch_size: int = 50,
    ) -> None:
        self._url = url
        self._batch_interval = batch_interval
        self._max_batch_size = max_batch_size
        self._buffer: deque[dict[str, Any]] = deque(maxlen=1000)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._start()

    def _start(self) -> None:
        self._thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._thread.start()

    def _flush_loop(self) -> None:
        while not self._stop.wait(self._batch_interval):
            self._flush()

    def _flush(self) -> None:
        with self._lock:
            if not self._buffer:
                return
            batch = list(self._buffer)
            self._buffer.clear()

        try:
            import urllib.request
            payload = json.dumps({"events": batch}).encode()
            req = urllib.request.Request(
                self._url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    def on_event(self, event: ProgressEvent) -> None:
        data = {
            "tracker": event.tracker_name,
            "n": event.n,
            "total": event.total,
            "elapsed": round(event.elapsed, 3),
            "state": event.state.value,
            "metrics": event.metrics_dict,
        }
        with self._lock:
            self._buffer.append(data)

    def on_close(self, tracker_name: str) -> None:
        self._flush()

    def stop(self) -> None:
        self._stop.set()
        self._flush()
        if self._thread:
            self._thread.join(timeout=2.0)


class FileLogHandler:
    """Append JSON-lines progress to a file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def on_event(self, event: ProgressEvent) -> None:
        data = {
            "timestamp": time.time(),
            "tracker": event.tracker_name,
            "n": event.n,
            "total": event.total,
            "elapsed": round(event.elapsed, 3),
            "state": event.state.value,
            "metrics": event.metrics_dict,
        }
        with open(self._path, "a") as f:
            f.write(json.dumps(data) + "\n")

    def on_close(self, tracker_name: str) -> None:
        pass


class LoggingHandler:
    """Bridge to Python's logging module."""

    def __init__(self, logger_name: str = "chugchug", level: int = logging.INFO) -> None:
        self._logger = logging.getLogger(logger_name)
        self._level = level

    def on_event(self, event: ProgressEvent) -> None:
        pct = ""
        if event.total and event.total > 0:
            pct = f" {100 * event.n / event.total:.1f}%"

        msg = f"[{event.desc or event.tracker_name}]{pct} {event.n}"
        if event.total:
            msg += f"/{event.total}"
        msg += f" [{format_time(event.elapsed)}]"

        if event.metrics:
            msg += " " + " ".join(f"{k}={v}" for k, v in event.metrics_dict.items())

        self._logger.log(self._level, msg, extra={"progress_event": event})

    def on_close(self, tracker_name: str) -> None:
        pass
