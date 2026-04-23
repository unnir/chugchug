"""Notebook progress bar handler — HTML/CSS gradient bars for Jupyter.

Uses IPython.display to render beautiful gradient progress bars directly
in notebook cells. The gradient is done via CSS linear-gradient, so it's
always perfectly smooth with zero rendering artifacts.

Usage:
    from chugchug import chug
    for item in chug(range(100), output="notebook", gradient="fire"):
        process(item)

Or auto-detected when running inside Jupyter:
    for item in chug(range(100)):
        process(item)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ._eta import create_eta
from ._format import format_count, format_rate, format_time
from ._gradient import get_gradient, GradientStops
from ._types import ProgressEvent, TrackerState


@dataclass
class _NotebookView:
    """Per-tracker state for notebook rendering."""
    name: str
    n: int = 0
    total: int | None = None
    elapsed: float = 0.0
    desc: str = ""
    metrics: dict[str, str] = field(default_factory=dict)
    state: TrackerState = TrackerState.IDLE
    eta_predictor: Any = field(default_factory=lambda: create_eta("adaptive"))
    last_render_time: float = 0.0
    display_id: str = ""
    displayed: bool = False
    # Speed tracking
    recent_rates: list[float] = field(default_factory=list)
    peak_rate: float = 0.0
    # Stall detection
    last_progress_n: int = 0
    last_progress_time: float = 0.0
    stall_seconds: float = 0.0

    def apply_event(self, event: ProgressEvent) -> None:
        now = time.monotonic()

        if event.n != self.n:
            self.last_progress_n = event.n
            self.last_progress_time = now
            self.stall_seconds = 0.0
        elif self.last_progress_time > 0:
            self.stall_seconds = now - self.last_progress_time
        elif self.n == 0 and event.n == 0:
            self.last_progress_time = now

        rate = self.eta_predictor.rate
        if rate is not None and rate > 0:
            self.recent_rates.append(rate)
            if len(self.recent_rates) > 20:
                self.recent_rates = self.recent_rates[-20:]
            if rate > self.peak_rate:
                self.peak_rate = rate

        self.n = event.n
        self.total = event.total
        self.elapsed = event.elapsed
        self.desc = event.desc
        self.metrics = event.metrics_dict
        self.state = event.state
        self.eta_predictor.update(event.n, event.timestamp)


def _gradient_css(stops: GradientStops) -> str:
    """Convert gradient stops to a CSS linear-gradient string."""
    if len(stops) == 1:
        r, g, b = stops[0]
        return f"rgb({r},{g},{b})"
    css_stops = []
    for i, (r, g, b) in enumerate(stops):
        pct = i / (len(stops) - 1) * 100
        css_stops.append(f"rgb({r},{g},{b}) {pct:.0f}%")
    return f"linear-gradient(to right, {', '.join(css_stops)})"


def _escape_html(text: str) -> str:
    """Minimal HTML escaping."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class NotebookHandler:
    """HTML/CSS gradient progress bars for Jupyter notebooks.

    Renders each tracker as a styled div with a CSS gradient fill.
    Updates in-place using IPython display IDs.
    """

    def __init__(
        self,
        min_interval: float = 0.1,
        gradient: str = "ocean",
        unit: str = "it",
        unit_scale: bool = False,
        show_metrics: bool = True,
        bar_width: int | str | None = None,
        eta_strategy: str = "adaptive",
        eta_window: int = 50,
        **kwargs: Any,
    ) -> None:
        self._min_interval = max(min_interval, 0.1)  # notebooks need >=100ms
        self._gradient = gradient
        self._unit = unit
        self._unit_scale = unit_scale
        self._show_metrics = show_metrics
        self._eta_strategy = eta_strategy
        self._eta_window = eta_window
        # Normalize bar_width: None/int → "100%", str kept as-is
        if bar_width is None or isinstance(bar_width, int):
            self._bar_width = "100%"
        else:
            self._bar_width = bar_width
        self._views: dict[str, _NotebookView] = {}
        self._counter = 0

    def on_event(self, event: ProgressEvent) -> None:
        name = event.tracker_name
        if name not in self._views:
            self._counter += 1
            view = _NotebookView(
                name=name,
                eta_predictor=create_eta(self._eta_strategy, self._eta_window),
                display_id=f"chugchug-{id(self)}-{self._counter}",
            )
            self._views[name] = view
            # Pre-register display slot immediately so first update is visible
            self._render(view, placeholder=True)

        view = self._views[name]
        view.apply_event(event)

        now = time.monotonic()
        if now - view.last_render_time < self._min_interval:
            return
        view.last_render_time = now

        self._render(view)

    def on_close(self, tracker_name: str) -> None:
        if tracker_name in self._views:
            view = self._views[tracker_name]
            view.state = TrackerState.COMPLETED
            self._render(view, final=True)
            self._views.pop(tracker_name, None)

    def _render(
        self, view: _NotebookView, final: bool = False, placeholder: bool = False,
    ) -> None:
        try:
            from IPython.display import display, HTML, update_display
        except ImportError:
            return

        if placeholder:
            # Pre-register the display slot with minimal content.
            # This ensures the first real update has a target to replace.
            html = f'<div id="{view.display_id}"></div>'
            display(HTML(html), display_id=view.display_id)
            view.displayed = True
            return

        html = self._build_html(view, final)
        obj = HTML(html)

        if not view.displayed:
            display(obj, display_id=view.display_id)
            view.displayed = True
        else:
            update_display(obj, display_id=view.display_id)

    def _build_html(self, view: _NotebookView, final: bool = False) -> str:
        """Build the HTML for a single progress bar."""
        stops = get_gradient(self._gradient)
        gradient_css = _gradient_css(stops)

        # ── Fraction ──
        if view.total and view.total > 0:
            frac = min(view.n / view.total, 1.0)
            pct = f"{100 * frac:.1f}%"
        else:
            frac = 0.0
            pct = ""

        pct_width = f"{100 * frac:.1f}%"

        # ── Text content ──
        text_parts: list[str] = []
        if view.desc:
            text_parts.append(f"<b>{_escape_html(view.desc)}</b>")

        if view.total and view.total > 0:
            if view.state == TrackerState.COMPLETED:
                text_parts.append(f"<b>done</b> {pct}")
            else:
                text_parts.append(pct)

            text_parts.append(format_count(view.n, view.total, self._unit_scale))

            eta_val = view.eta_predictor.eta(view.n, view.total)
            text_parts.append(
                f"[{format_time(view.elapsed)}&lt;{format_time(eta_val)}]"
            )

            rate = view.eta_predictor.rate
            text_parts.append(format_rate(rate, self._unit, self._unit_scale))
        else:
            text_parts.append(f"{view.n}")
            text_parts.append(f"[{format_time(view.elapsed)}]")
            rate = view.eta_predictor.rate
            text_parts.append(format_rate(rate, self._unit, self._unit_scale))

        # Stall warning
        if view.stall_seconds >= 10.0 and view.state == TrackerState.RUNNING:
            text_parts.append(
                f'<span style="color:#ffaa00">! STALLED {format_time(view.stall_seconds)}</span>'
            )

        # Metrics
        if view.metrics and self._show_metrics:
            metric_strs = []
            for k, v in view.metrics.items():
                metric_strs.append(f"{_escape_html(k)}={_escape_html(v)}")
            text_parts.append(
                f'<span style="opacity:0.7">| {" ".join(metric_strs)}</span>'
            )

        text_html = " &nbsp; ".join(text_parts)

        # ── Chug styling ──
        if view.state == TrackerState.COMPLETED:
            # Completion: green tint overlay
            bar_bg = f"""
                background: linear-gradient(
                    to right,
                    rgba(0,255,100,0.25),
                    rgba(0,255,100,0.25)
                ), {gradient_css};
            """
            border_color = "#00cc66"
        elif view.stall_seconds >= 10.0:
            bar_bg = f"""
                background: linear-gradient(
                    to right,
                    rgba(255,180,0,0.3),
                    rgba(255,180,0,0.3)
                ), {gradient_css};
            """
            border_color = "#ffaa00"
        else:
            bar_bg = f"background: {gradient_css};"
            border_color = "transparent"

        # ── Trough color ──
        trough_css = "rgb(40,40,48)"

        # ── Summary line ──
        summary_html = ""
        if final and view.elapsed > 0.5:
            avg_rate = view.n / view.elapsed if view.elapsed > 0 else 0
            summary_parts = [f"Done in {format_time(view.elapsed)}"]
            summary_parts.append(
                f"avg {format_rate(avg_rate, self._unit, self._unit_scale)}"
            )
            if view.peak_rate > avg_rate * 1.1:
                summary_parts.append(
                    f"peak {format_rate(view.peak_rate, self._unit, self._unit_scale)}"
                )
            summary_html = f"""
                <div style="
                    font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
                    font-size: 11px;
                    color: #888;
                    padding: 2px 0 0 4px;
                ">{' | '.join(summary_parts)}</div>
            """

        # ── Assemble HTML ──
        return f"""
        <div style="margin: 4px 0; width: {self._bar_width};">
            <div style="
                position: relative;
                height: 26px;
                background: {trough_css};
                border-radius: 5px;
                overflow: hidden;
                border: 1px solid {border_color};
                box-shadow: inset 0 1px 3px rgba(0,0,0,0.3);
            ">
                <div style="
                    position: absolute;
                    top: 0; left: 0; bottom: 0;
                    width: {pct_width};
                    {bar_bg}
                    border-radius: 4px 0 0 4px;
                    transition: width 0.15s ease-out;
                "></div>
                <div style="
                    position: relative;
                    padding: 4px 8px;
                    color: white;
                    font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
                    font-size: 12px;
                    white-space: nowrap;
                    text-shadow: 0 1px 2px rgba(0,0,0,0.6);
                    line-height: 18px;
                ">{text_html}</div>
            </div>
            {summary_html}
        </div>
        """
