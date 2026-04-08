"""Display handlers — render progress events to various outputs.

Each handler accumulates per-tracker state (TrackerView) and renders
on its own schedule. Render throttling happens here, not in trackers.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from typing import Any, TextIO

from ._eta import AdaptiveETA, create_eta
from ._format import format_count, format_rate, format_time
from ._gradient import (
    _brighten,
    _lerp_multi,
    _render_ascii,
    _tint,
    get_gradient,
)
from ._terminal import ColorDepth, TerminalInfo, get_terminal_info
from ._types import HandlerProtocol, ProgressEvent, TrackerState


# ─── Trough color for the empty portion of the bar ──────────────────────────
_TROUGH = (35, 35, 40)

_RESET = "\033[0m"


@dataclass
class TrackerView:
    """Per-tracker accumulated state within a handler."""
    name: str
    n: int = 0
    total: int | None = None
    elapsed: float = 0.0
    desc: str = ""
    metrics: dict[str, str] = field(default_factory=dict)
    state: TrackerState = TrackerState.IDLE
    eta_predictor: Any = field(default_factory=lambda: create_eta("adaptive"))
    last_render_time: float = 0.0
    # Stall detection
    last_progress_n: int = 0
    last_progress_time: float = 0.0
    stall_seconds: float = 0.0
    # Speed trend
    recent_rates: list[float] = field(default_factory=list)
    # Completion animation
    completed_at: float = 0.0
    # Metric trend tracking (for auto-coloring)
    prev_metrics: dict[str, float] = field(default_factory=dict)
    # Peak speed
    peak_rate: float = 0.0

    def apply_event(self, event: ProgressEvent) -> None:
        now = time.monotonic()

        # Track stall: detect when n hasn't changed
        if event.n != self.n:
            self.last_progress_n = event.n
            self.last_progress_time = now
            self.stall_seconds = 0.0
        elif self.last_progress_time > 0:
            self.stall_seconds = now - self.last_progress_time
        elif self.n == 0 and event.n == 0:
            self.last_progress_time = now

        # Track speed trend (keep last 20 rate samples)
        rate = self.eta_predictor.rate
        if rate is not None and rate > 0:
            self.recent_rates.append(rate)
            if len(self.recent_rates) > 20:
                self.recent_rates = self.recent_rates[-20:]
            if rate > self.peak_rate:
                self.peak_rate = rate

        # Track completion moment
        if event.state == TrackerState.COMPLETED and self.state != TrackerState.COMPLETED:
            self.completed_at = now

        # Track metric trends
        new_metrics = event.metrics_dict
        for k, v in new_metrics.items():
            try:
                val = float(v.rstrip("%"))
                self.prev_metrics[k] = val
            except (ValueError, AttributeError):
                pass

        self.n = event.n
        self.total = event.total
        self.elapsed = event.elapsed
        self.desc = event.desc
        self.metrics = new_metrics
        self.state = event.state
        self.eta_predictor.update(event.n, event.timestamp)

    @property
    def speed_trend(self) -> str:
        rates = self.recent_rates
        if len(rates) < 6:
            return ""
        recent_avg = sum(rates[-3:]) / 3
        older_avg = sum(rates[-6:-3]) / 3
        if older_avg == 0:
            return ""
        ratio = recent_avg / older_avg
        if ratio > 1.15:
            return "\u2191"  # ↑
        if ratio < 0.85:
            return "\u2193"  # ↓
        return "\u2192"  # →

    @property
    def is_stalled(self) -> bool:
        return self.stall_seconds >= 10.0 and self.state == TrackerState.RUNNING

    @property
    def just_completed(self) -> bool:
        if self.completed_at == 0:
            return False
        return (time.monotonic() - self.completed_at) < 0.5


class TTYHandler:
    """Full-width gradient bar with embedded text.

    The entire terminal line becomes the progress bar. The gradient
    background sweeps left-to-right as progress advances, and all text
    (description, percentage, speed, metrics) is rendered on top.

    Filled portion:  gradient background + bold white text
    Empty portion:   dark trough background + dim text
    """

    def __init__(
        self,
        file: TextIO | None = None,
        min_interval: float = 0.05,
        gradient: str = "ocean",
        ascii_mode: bool = False,
        bar_width: int | None = None,
        unit: str = "it",
        unit_scale: bool = False,
        show_metrics: bool = True,
    ) -> None:
        self._file = file or sys.stderr
        self._min_interval = min_interval
        self._gradient = gradient
        self._ascii_mode = ascii_mode
        self._unit = unit
        self._unit_scale = unit_scale
        self._show_metrics = show_metrics
        self._views: dict[str, TrackerView] = {}
        self._view_order: list[str] = []
        self._terminal = get_terminal_info(self._file)
        self._bar_width = bar_width or max(10, self._terminal.width - 50)
        self._last_num_lines = 0

    def on_event(self, event: ProgressEvent) -> None:
        name = event.tracker_name
        if name not in self._views:
            self._views[name] = TrackerView(name=name)
            self._view_order.append(name)

        view = self._views[name]
        view.apply_event(event)

        now = time.monotonic()
        if now - view.last_render_time < self._min_interval:
            return
        view.last_render_time = now

        self._render()

    def on_close(self, tracker_name: str) -> None:
        if tracker_name in self._views:
            view = self._views[tracker_name]
            view.state = TrackerState.COMPLETED
            self._render()
            if len(self._view_order) == 1:
                # Hard reset before newline — no bg color can leak
                self._file.write("\033[0m\n")
                summary = self._format_summary(view)
                if summary:
                    self._file.write(summary + "\n")
                self._file.flush()
            self._views.pop(tracker_name, None)
            if tracker_name in self._view_order:
                self._view_order.remove(tracker_name)

    def _render(self) -> None:
        f = self._file

        # Always reset ANSI state first — prevents leaked background colors
        # from wrapping or previous renders from accumulating.
        f.write("\033[0m")

        if self._last_num_lines > 1:
            f.write(f"\033[{self._last_num_lines - 1}A\r")

        lines: list[str] = []
        for name in self._view_order:
            view = self._views.get(name)
            if view is None:
                continue
            line = self._format_line(view)
            lines.append(line)

        if len(lines) <= 1:
            if lines:
                f.write(f"\r\033[0m{lines[0]}\033[0m\033[K")
            self._last_num_lines = 1
        else:
            for i, line in enumerate(lines):
                f.write(f"\r\033[0m{line}\033[0m\033[K")
                if i < len(lines) - 1:
                    f.write("\n")
            self._last_num_lines = len(lines)

        f.flush()

    def _format_line(self, view: TrackerView) -> str:
        """Build the progress line.

        For color terminals: full-width gradient background with embedded text.
        For ASCII/no-color: classic separate-bar layout.
        """
        is_tc = self._terminal.color_depth == ColorDepth.TRUECOLOR
        is_256 = self._terminal.color_depth == ColorDepth.EXTENDED

        if (is_tc or is_256) and not self._ascii_mode:
            return self._format_embedded(view, is_tc)
        else:
            return self._format_classic(view)

    # ─── Embedded full-width style (color terminals) ─────────────────────

    def _format_embedded(self, view: TrackerView, is_truecolor: bool) -> str:
        """The entire line is the bar. Gradient bg = filled, trough bg = empty."""
        stops = get_gradient(self._gradient)
        # Hard cap + margin. shutil.get_terminal_size() can return wrong
        # values in VS Code, tmux, or resized terminals. If the bar is even
        # 1 char too wide, the terminal wraps and background colors bleed
        # into every subsequent line — catastrophic.
        detected = self._terminal.width
        width = max(40, min(detected - 4, 120))

        # ── Build PURE ASCII text (no Unicode → no ambiguous-width chars) ──
        text = self._build_text(view)

        # Pad or truncate to exact width
        if len(text) < width:
            text = text + " " * (width - len(text))
        elif len(text) > width:
            text = text[:width]

        # ── Compute fill fraction ──
        if view.total and view.total > 0:
            frac = min(view.n / view.total, 1.0)
        else:
            # Spinner mode: no fill, just trough with pulsing accent
            frac = 0.0

        filled = int(frac * width)

        # ── Render with minimal ANSI escapes ──
        # ANSI bg color persists until changed. We only emit a new escape
        # when the quantized color or fg style actually changes. This cuts
        # escape sequences from ~120 per line to ~15-25 — fast enough for
        # VS Code's terminal which chokes on rapid ANSI output.

        if not is_truecolor:
            from ._gradient import _rgb_to_256

        last_escape = None
        chars: list[str] = []

        for i, ch in enumerate(text):
            if i < filled:
                color_t = i / max(width - 1, 1)
                bg_color = _lerp_multi(stops, color_t)

                # State tints
                if view.just_completed:
                    bg_color = _tint(bg_color, (0, 255, 100), 0.4)
                    bg_color = _brighten(bg_color, 0.2)
                elif view.is_stalled:
                    bg_color = _tint(bg_color, (255, 180, 0), 0.4)

                # Leading edge glow
                if view.state == TrackerState.RUNNING and filled - i <= 2:
                    bg_color = _brighten(bg_color, 0.15)

                # Adaptive contrast
                lum = 0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]
                fg = "1;30" if lum > 160 else "1;97"

                # Quantize RGB to nearest 8 — only emit escape when it
                # visually changes (imperceptible difference, huge perf win)
                r, g, b = bg_color
                key = (r >> 3, g >> 3, b >> 3, fg)

                if key != last_escape:
                    if is_truecolor:
                        chars.append(f"\033[48;2;{r};{g};{b};{fg}m{ch}")
                    else:
                        chars.append(f"\033[48;5;{_rgb_to_256(r, g, b)};{fg}m{ch}")
                    last_escape = key
                else:
                    chars.append(ch)
            else:
                if last_escape != "trough":
                    chars.append(f"\033[48;2;{_TROUGH[0]};{_TROUGH[1]};{_TROUGH[2]};22;90m{ch}")
                    last_escape = "trough"
                else:
                    chars.append(ch)

        return "".join(chars) + _RESET

    def _build_text(self, view: TrackerView) -> str:
        """Build PURE ASCII text for the embedded bar line.

        Every character must be single-width ASCII. Unicode characters like
        checkmarks, arrows, box-drawing, and braille have ambiguous widths
        across terminals/fonts — if even one renders as double-width, the
        bar exceeds terminal width, wraps, and background colors bleed into
        subsequent lines.
        """
        parts: list[str] = []

        if view.desc:
            parts.append(f" {view.desc}")

        if view.total is not None and view.total > 0:
            frac = min(view.n / view.total, 1.0)

            if view.state == TrackerState.COMPLETED:
                parts.append(f"  * {100 * frac:.0f}%")
            else:
                parts.append(f"  {100 * frac:5.1f}%")

            parts.append(f"  {format_count(view.n, view.total, self._unit_scale)}")

            eta_val = view.eta_predictor.eta(view.n, view.total)
            parts.append(f"  [{format_time(view.elapsed)}<{format_time(eta_val)}]")

            rate_str = format_rate(view.eta_predictor.rate, self._unit, self._unit_scale)
            trend = view.speed_trend
            if trend:
                # ASCII trend indicators
                trend = {"↑": "^", "↓": "v", "→": "-"}.get(trend, "")
                rate_str += trend
            parts.append(f"  {rate_str}")
        else:
            # Spinner: ASCII only
            spinner = "-\\|/"
            idx = int(view.elapsed * 8) % len(spinner)
            parts.append(f"  {spinner[idx]} {view.n}")
            parts.append(f"  [{format_time(view.elapsed)}]")
            rate_str = format_rate(view.eta_predictor.rate, self._unit, self._unit_scale)
            trend = view.speed_trend
            if trend:
                trend = {"↑": "^", "↓": "v", "→": "-"}.get(trend, "")
                rate_str += trend
            parts.append(f"  {rate_str}")

        if view.is_stalled:
            parts.append(f"  ! STALLED {format_time(view.stall_seconds)}")

        if view.metrics and self._show_metrics:
            metric_str = "  ".join(f"{k}={v}" for k, v in view.metrics.items())
            parts.append(f"  | {metric_str}")

        return "".join(parts)

    # ─── Classic style (ASCII / no-color fallback) ───────────────────────

    def _format_classic(self, view: TrackerView) -> str:
        """Classic layout: description  pct  [bar]  count  time  rate.

        The bar width is computed dynamically — the text parts are measured
        first and the bar fills whatever space remains. This prevents line
        wrapping when counts or rates are large (e.g. 1000000/1000000).
        """
        has_color = self._terminal.color_depth != ColorDepth.NONE
        term_width = self._terminal.width

        # ── Build text parts (everything except the bar) ──
        left: list[str] = []   # before bar
        right: list[str] = []  # after bar

        if view.desc:
            left.append(view.desc)

        # ASCII-only text so len() == visual width (no ambiguous-width Unicode)
        _trend_ascii = {"\u2191": "^", "\u2193": "v", "\u2192": "-"}

        if view.total is not None and view.total > 0:
            frac = min(view.n / view.total, 1.0)
            if view.state == TrackerState.COMPLETED:
                pct = "* 100%"
            else:
                pct = f"{100 * frac:5.1f}%"
            left.append(pct)

            right.append(format_count(view.n, view.total, self._unit_scale))
            eta_val = view.eta_predictor.eta(view.n, view.total)
            right.append(f"[{format_time(view.elapsed)}<{format_time(eta_val)}]")
            rate_str = format_rate(view.eta_predictor.rate, self._unit, self._unit_scale)
            trend = view.speed_trend
            if trend:
                rate_str += _trend_ascii.get(trend, "")
            right.append(rate_str)
        else:
            frac = 0.0
            spinner = "-\\|/"
            idx = int(view.elapsed * 8) % len(spinner)
            left.append(f"{spinner[idx]} {view.n}")
            right.append(f"[{format_time(view.elapsed)}]")
            rate_str = format_rate(view.eta_predictor.rate, self._unit, self._unit_scale)
            trend = view.speed_trend
            if trend:
                rate_str += _trend_ascii.get(trend, "")
            right.append(rate_str)

        if view.is_stalled:
            right.append(f"! STALLED {format_time(view.stall_seconds)}")

        if view.metrics and self._show_metrics:
            metrics_str = " ".join(f"{k}={v}" for k, v in view.metrics.items())
            right.append(f"| {metrics_str}")

        left_str = " ".join(left)
        right_str = " ".join(right)

        # ── Compute bar width from remaining space ──
        # Layout: "{left} [{bar}] {right}"
        # Overhead: 2 spaces (before [ and after ]) + 2 brackets
        text_len = len(left_str) + len(right_str) + 4
        bar_width = term_width - text_len

        if view.total is not None and view.total > 0 and bar_width >= 10:
            bar = _render_ascii(frac, bar_width)
            return f"{left_str} {bar} {right_str}"

        # Not enough room for bar — text only
        if view.total is not None and view.total > 0:
            return f"{left_str} {right_str}"
        return f"{left_str} {right_str}"

    # ─── Completion summary ──────────────────────────────────────────────

    def _format_summary(self, view: TrackerView) -> str:
        has_color = self._terminal.color_depth != ColorDepth.NONE
        if view.elapsed <= 0.5:
            return ""

        avg_rate = view.n / view.elapsed if view.elapsed > 0 else 0
        peak = view.peak_rate

        DIM = "\033[2m" if has_color else ""
        RESET = "\033[0m" if has_color else ""

        parts = [f"{DIM}  Done in {format_time(view.elapsed)}"]
        parts.append(f"avg {format_rate(avg_rate, self._unit, self._unit_scale)}")
        if peak > 0 and peak > avg_rate * 1.1:
            parts.append(f"peak {format_rate(peak, self._unit, self._unit_scale)}")
        return f"{' | '.join(parts)}{RESET}"


class JSONHandler:
    """One JSON line per event — for CI/CD and structured logging."""

    def __init__(self, file: TextIO | None = None) -> None:
        self._file = file or sys.stderr

    def on_event(self, event: ProgressEvent) -> None:
        data = {
            "tracker": event.tracker_name,
            "n": event.n,
            "total": event.total,
            "elapsed": round(event.elapsed, 3),
            "desc": event.desc,
            "metrics": event.metrics_dict,
            "state": event.state.value,
        }
        if event.total and event.total > 0:
            data["percentage"] = round(100 * event.n / event.total, 2)
        self._file.write(json.dumps(data) + "\n")
        self._file.flush()

    def on_close(self, tracker_name: str) -> None:
        pass


class LOGHandler:
    """Human-readable log lines — one per event (throttled)."""

    def __init__(
        self,
        file: TextIO | None = None,
        min_interval: float = 1.0,
    ) -> None:
        self._file = file or sys.stderr
        self._min_interval = min_interval
        self._last_times: dict[str, float] = {}

    def on_event(self, event: ProgressEvent) -> None:
        now = time.monotonic()
        last = self._last_times.get(event.tracker_name, 0.0)
        if now - last < self._min_interval and event.state == TrackerState.RUNNING:
            return
        self._last_times[event.tracker_name] = now

        if event.total:
            pct = f"{100 * event.n / event.total:.1f}%"
            msg = f"[{event.desc or event.tracker_name}] {pct} ({event.n}/{event.total}) [{format_time(event.elapsed)}]"
        else:
            msg = f"[{event.desc or event.tracker_name}] {event.n} [{format_time(event.elapsed)}]"

        if event.metrics:
            msg += " " + " ".join(f"{k}={v}" for k, v in event.metrics_dict.items())

        self._file.write(msg + "\n")
        self._file.flush()

    def on_close(self, tracker_name: str) -> None:
        self._last_times.pop(tracker_name, None)


class SilentHandler:
    """No-op handler — for tracking only, no output."""

    def on_event(self, event: ProgressEvent) -> None:
        pass

    def on_close(self, tracker_name: str) -> None:
        pass
