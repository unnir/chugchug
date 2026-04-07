"""Bar rendering with gradient colors and graceful degradation.

Core technique: background-colored spaces instead of Unicode block characters.
A space is always exactly one character wide in every font, terminal, and
notebook. The background color fills the entire cell with zero rendering
artifacts.
"""

from __future__ import annotations

import math
import time

from ._terminal import ColorDepth, TerminalInfo


# ─── Types ───────────────────────────────────────────────────────────────────

GradientStops = list[tuple[int, int, int]]

# ─── Gradient Presets ─────────────────────────────────────────────────────────

GRADIENTS: dict[str, GradientStops] = {
    # Classic 2-stop gradients
    "ocean":  [(30, 144, 255), (0, 255, 200)],
    "fire":   [(255, 69, 0), (255, 215, 0)],
    "forest": [(34, 139, 34), (144, 238, 144)],
    "purple": [(138, 43, 226), (255, 105, 180)],
    "mono":   [(120, 120, 120), (255, 255, 255)],
    "cyber":  [(0, 255, 136), (0, 200, 255)],
    # Multi-stop gradients
    "rainbow": [
        (255, 0, 80), (255, 130, 0), (255, 220, 0),
        (0, 220, 60), (0, 160, 255), (140, 0, 255),
    ],
    "heatmap": [
        (0, 40, 200), (0, 180, 200), (0, 210, 60),
        (255, 240, 0), (255, 80, 0),
    ],
    "candy": [
        (255, 80, 180), (200, 60, 255), (80, 180, 255),
        (180, 255, 120), (255, 160, 80), (255, 80, 180),
    ],
    "neon": [
        (255, 0, 255), (0, 255, 255), (255, 255, 0), (255, 0, 255),
    ],
    "aurora": [
        (0, 40, 80), (0, 200, 100), (100, 255, 200),
        (200, 100, 255), (60, 0, 120),
    ],
    "sunset": [
        (20, 0, 80), (140, 0, 120), (255, 60, 60),
        (255, 160, 40), (255, 220, 80),
    ],
    "matrix": [
        (0, 40, 0), (0, 180, 0), (80, 255, 80), (0, 180, 0), (0, 60, 0),
    ],
    "ice": [
        (200, 230, 255), (100, 180, 255), (40, 100, 220),
        (100, 180, 255), (200, 240, 255),
    ],
}

_custom_gradients: dict[str, GradientStops] = {}


def register_gradient(
    name: str,
    start: tuple[int, int, int],
    end: tuple[int, int, int],
) -> None:
    """Register a custom 2-stop gradient preset."""
    _custom_gradients[name] = [start, end]


def register_multi_gradient(
    name: str,
    stops: list[tuple[int, int, int]],
) -> None:
    """Register a custom multi-stop gradient preset."""
    if len(stops) < 2:
        raise ValueError("Gradient needs at least 2 color stops")
    _custom_gradients[name] = list(stops)


def get_gradient(name: str) -> GradientStops:
    """Get gradient stops by name, checking custom gradients first."""
    if name in _custom_gradients:
        return _custom_gradients[name]
    return GRADIENTS.get(name, GRADIENTS["ocean"])


# ─── Color Helpers ────────────────────────────────────────────────────────────

def _rgb(r: int, g: int, b: int) -> str:
    """Foreground truecolor."""
    return f"\033[38;2;{r};{g};{b}m"


def _bg_rgb(r: int, g: int, b: int) -> str:
    """Background truecolor."""
    return f"\033[48;2;{r};{g};{b}m"


def _lerp_color(
    c1: tuple[int, int, int],
    c2: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    """Linear interpolation between two RGB colors."""
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _lerp_multi(stops: GradientStops, t: float) -> tuple[int, int, int]:
    """Interpolate across N color stops at position t (0..1)."""
    if len(stops) == 1:
        return stops[0]
    t = max(0.0, min(1.0, t))
    n = len(stops) - 1
    idx = t * n
    lo = int(idx)
    if lo >= n:
        return stops[-1]
    frac = idx - lo
    return _lerp_color(stops[lo], stops[lo + 1], frac)


def _brighten(
    color: tuple[int, int, int],
    intensity: float,
) -> tuple[int, int, int]:
    """Brighten a color toward white by intensity (0..1)."""
    return (
        min(255, int(color[0] + (255 - color[0]) * intensity)),
        min(255, int(color[1] + (255 - color[1]) * intensity)),
        min(255, int(color[2] + (255 - color[2]) * intensity)),
    )


def _tint(
    color: tuple[int, int, int],
    target: tuple[int, int, int],
    strength: float,
) -> tuple[int, int, int]:
    """Tint a color toward a target color by strength (0..1)."""
    return _lerp_color(color, target, strength)


def _dim(
    color: tuple[int, int, int],
    factor: float,
) -> tuple[int, int, int]:
    """Dim a color by factor (0..1 where 0=black, 1=unchanged)."""
    return (
        int(color[0] * factor),
        int(color[1] * factor),
        int(color[2] * factor),
    )


_RESET = "\033[0m"
_BG_RESET = "\033[49m"

# ─── 256-Color Approximation ─────────────────────────────────────────────────

def _rgb_to_256(r: int, g: int, b: int) -> int:
    """Approximate RGB to nearest 256-color index."""
    if r == g == b:
        if r < 8:
            return 16
        if r > 248:
            return 231
        return round((r - 8) / 247 * 24) + 232
    return (
        16
        + (36 * round(r / 255 * 5))
        + (6 * round(g / 255 * 5))
        + round(b / 255 * 5)
    )


def _fg256(r: int, g: int, b: int) -> str:
    return f"\033[38;5;{_rgb_to_256(r, g, b)}m"


def _bg256(r: int, g: int, b: int) -> str:
    return f"\033[48;5;{_rgb_to_256(r, g, b)}m"


# ─── Sparkline (utility, not used in default bar) ───────────────────────────

SPARKLINE_CHARS = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"


def render_sparkline(
    values: list[float],
    width: int = 8,
    color_start: tuple[int, int, int] | None = None,
    color_end: tuple[int, int, int] | None = None,
    color_fn=None,
) -> str:
    """Render a sparkline from a list of values.

    Returns a string of `width` characters using Unicode block elements.
    Optionally colored with a gradient from color_start to color_end.
    """
    if len(values) < 2:
        return ""
    samples = values[-width:]
    mn, mx = min(samples), max(samples)

    chars: list[str] = []
    for i, v in enumerate(samples):
        if mx == mn:
            idx = 3
        else:
            idx = int((v - mn) / (mx - mn) * 7)
        ch = SPARKLINE_CHARS[idx]
        if color_fn and color_start and color_end:
            t = i / max(len(samples) - 1, 1)
            r, g, b = _lerp_color(color_start, color_end, t)
            chars.append(f"{color_fn(r, g, b)}{ch}")
        else:
            chars.append(ch)

    result = "".join(chars)
    if color_fn and color_start:
        result += _RESET
    return result


# ─── Chug Rendering ────────────────────────────────────────────────────────────

# Trough color — subtle dark gray visible against most terminal backgrounds
_TROUGH = (40, 40, 45)


def render_bar(
    fraction: float,
    width: int,
    gradient: str = "ocean",
    terminal: TerminalInfo | None = None,
    stalled: bool = False,
    completed: bool = False,
) -> str:
    """Render a progress bar using background-colored spaces.

    This technique avoids ALL Unicode block character rendering issues:
    - No font-dependent glyph widths
    - No sub-pixel gaps between adjacent blocks
    - Works identically in every terminal, font, and notebook

    Each character is a plain space with a background color set via ANSI.
    Filled positions get the gradient color as background.
    Empty positions get a subtle dark trough background.

    Degrades: truecolor -> 256-color -> basic-16 -> ASCII.
    """
    fraction = max(0.0, min(1.0, fraction))

    if terminal is None:
        from ._terminal import get_terminal_info
        terminal = get_terminal_info()

    # ASCII fallback (no color support or no unicode)
    if not terminal.unicode_support or terminal.color_depth == ColorDepth.NONE:
        return _render_ascii(fraction, width)

    # Basic 16-color — use simple block approach (no gradient)
    if terminal.color_depth == ColorDepth.BASIC:
        return _render_basic16(fraction, width)

    # ── Truecolor or 256-color: background-colored spaces ──
    stops = get_gradient(gradient)

    if terminal.color_depth == ColorDepth.TRUECOLOR:
        bg_fn = _bg_rgb
    else:
        bg_fn = _bg256

    filled_int = int(fraction * width)
    now = time.monotonic()

    # State tint colors
    AMBER = (255, 180, 0)
    GREEN = (0, 255, 100)

    chars: list[str] = []
    for i in range(width):
        color_t = i / max(width - 1, 1)
        base_color = _lerp_multi(stops, color_t)

        if i < filled_int:
            # Filled — gradient background on a space
            color = base_color
            if completed:
                color = _tint(color, GREEN, 0.5)
                color = _brighten(color, 0.3)
            elif stalled:
                breath = 0.15 + 0.1 * math.sin(now * 2.0)
                color = _tint(color, AMBER, breath + 0.3)
            chars.append(f"{bg_fn(*color)} ")
        else:
            # Empty — dark trough background
            chars.append(f"{bg_fn(*_TROUGH)} ")

    return f"{''.join(chars)}{_BG_RESET}"


def _render_basic16(fraction: float, width: int) -> str:
    """Basic 16-color bar using ANSI background colors."""
    filled = int(fraction * width)
    # Green background for filled, dark gray for empty
    bar = f"\033[42m{' ' * filled}\033[100m{' ' * (width - filled)}\033[49m"
    return bar


def _render_ascii(fraction: float, width: int) -> str:
    """Pure ASCII bar: [====   ]"""
    filled = int(fraction * width)
    bar = "=" * filled + " " * (width - filled)
    return f"[{bar}]"
