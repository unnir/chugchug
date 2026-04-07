"""Terminal-native charts and visualizations using background-colored spaces.

Every character cell = one colored pixel. This technique produces perfectly
clean output in any terminal, font, or notebook that supports ANSI colors.
Uses the same gradient presets as chugchug progress bars.

Usage:
    from chugchug.viz import line_chart, bar_chart, heatmap

    # Loss curve
    print(line_chart(losses, title="Loss", gradient="fire"))

    # Throughput comparison
    print(bar_chart({"GPU": 1500, "CPU": 400}, gradient="cyber"))

    # Confusion matrix
    print(heatmap(matrix, labels=["cat", "dog", "bird"], gradient="fire"))
"""

from __future__ import annotations

from ._gradient import (
    _bg_rgb,
    _bg256,
    _brighten,
    _dim,
    _lerp_multi,
    _rgb,
    _fg256,
    _RESET,
    _BG_RESET,
    get_gradient,
    GradientStops,
)
from ._terminal import ColorDepth, get_terminal_info


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_color_fns() -> tuple:
    """Return (bg_fn, fg_fn, has_color) based on terminal capabilities."""
    terminal = get_terminal_info()
    if terminal.color_depth == ColorDepth.TRUECOLOR:
        return _bg_rgb, _rgb, True
    elif terminal.color_depth == ColorDepth.EXTENDED:
        return _bg256, _fg256, True
    return None, None, False


def _resample(values: list[float], width: int) -> list[float]:
    """Resample a list of values to exactly `width` points via linear interp."""
    n = len(values)
    if n == 0:
        return [0.0] * width
    if n == 1:
        return [values[0]] * width
    if n == width:
        return list(values)
    result = []
    for i in range(width):
        t = i / max(width - 1, 1) * (n - 1)
        lo = int(t)
        hi = min(lo + 1, n - 1)
        frac = t - lo
        result.append(values[lo] + (values[hi] - values[lo]) * frac)
    return result


def _format_label(val: float, width: int = 6) -> str:
    """Format a numeric label to a fixed width."""
    if abs(val) >= 1000:
        s = f"{val:.0f}"
    elif abs(val) >= 10:
        s = f"{val:.1f}"
    elif abs(val) >= 1:
        s = f"{val:.2f}"
    else:
        s = f"{val:.3f}"
    return s.rjust(width)


# ─── Line Chart (Filled Area) ───────────────────────────────────────────────

def line_chart(
    values: list[float],
    width: int = 60,
    height: int = 10,
    gradient: str = "ocean",
    title: str = "",
    filled: bool = True,
    show_axis: bool = True,
) -> str:
    """Render a filled area chart using background-colored spaces.

    Each column maps to a data point. Filled cells below the line get
    gradient coloring with brightness fading toward the bottom.

    Args:
        values: Data points to plot.
        width: Chart width in characters (excluding axis labels).
        height: Chart height in rows.
        gradient: Gradient preset name.
        title: Optional title above the chart.
        filled: If True, fill area below the line. If False, line only.
        show_axis: Show Y-axis labels and border.

    Returns:
        Multi-line string ready to print.
    """
    if not values:
        return ""

    bg_fn, fg_fn, has_color = _get_color_fns()

    # Resample data to chart width
    data = _resample(values, width)
    mn, mx = min(data), max(data)
    if mn == mx:
        mx = mn + 1.0

    val_range = mx - mn
    stops = get_gradient(gradient)

    # Axis label width
    label_w = 7 if show_axis else 0

    lines: list[str] = []
    if title:
        lines.append(f"{'':>{label_w}}  {title}")

    for row in range(height):
        # What value does this row represent?
        # row=0 is top (max), row=height-1 is bottom (min)
        row_val = mx - (row / max(height - 1, 1)) * val_range

        # Y-axis label (show for first, middle, last row)
        if show_axis and row in (0, height // 2, height - 1):
            label = _format_label(row_val, label_w)
        elif show_axis:
            label = " " * label_w
        else:
            label = ""

        # Axis border
        border = " \u2524" if show_axis else ""  # ┤

        # Chart cells
        chars: list[str] = []
        for col in range(width):
            val = data[col]

            # Which row does this data point fall on? (fractional)
            data_row = (mx - val) / val_range * (height - 1)

            if filled:
                if row >= data_row:
                    # Filled: this cell is at or below the data line
                    color_t = col / max(width - 1, 1)
                    color = _lerp_multi(stops, color_t)

                    # Brightness: brightest at the data line, fading to bottom
                    if row <= data_row + 0.5:
                        # At the line itself — full brightness
                        brightness = 1.0
                    else:
                        # Below the line — fade
                        depth = (row - data_row) / max(height - 1, 1)
                        brightness = max(0.25, 1.0 - depth * 1.2)

                    color = _dim(color, brightness)

                    if has_color and bg_fn:
                        chars.append(f"{bg_fn(*color)} ")
                    else:
                        chars.append("#")
                else:
                    chars.append(" ")
            else:
                # Line only — draw at the data row
                if abs(row - data_row) < 0.6:
                    color_t = col / max(width - 1, 1)
                    color = _lerp_multi(stops, color_t)
                    if has_color and bg_fn:
                        chars.append(f"{bg_fn(*color)} ")
                    else:
                        chars.append("*")
                else:
                    chars.append(" ")

        row_str = "".join(chars)
        if has_color:
            row_str += _BG_RESET
        lines.append(f"{label}{border}{row_str}")

    # Bottom axis line
    if show_axis:
        lines.append(f"{'':>{label_w}} \u2514{'─' * width}")  # └───

    return "\n".join(lines)


# ─── Multi-Line Chart ────────────────────────────────────────────────────────

def multi_line_chart(
    series: dict[str, list[float]],
    width: int = 60,
    height: int = 10,
    gradient: str = "rainbow",
    title: str = "",
    show_axis: bool = True,
) -> str:
    """Render multiple line series on the same chart.

    Each series gets a distinct color from the gradient. Lines are drawn
    as single-pixel traces (not filled).

    Args:
        series: Dict of {name: values}.
        width: Chart width.
        height: Chart height.
        gradient: Gradient for assigning series colors.
        title: Optional title.
        show_axis: Show Y-axis labels.

    Returns:
        Multi-line string ready to print.
    """
    if not series:
        return ""

    bg_fn, fg_fn, has_color = _get_color_fns()
    stops = get_gradient(gradient)
    names = list(series.keys())

    # Resample all series
    resampled: dict[str, list[float]] = {}
    all_vals: list[float] = []
    for name, vals in series.items():
        r = _resample(vals, width)
        resampled[name] = r
        all_vals.extend(r)

    mn, mx = min(all_vals), max(all_vals)
    if mn == mx:
        mx = mn + 1.0
    val_range = mx - mn

    # Assign colors to each series
    series_colors: dict[str, tuple[int, int, int]] = {}
    for i, name in enumerate(names):
        t = i / max(len(names) - 1, 1)
        series_colors[name] = _lerp_multi(stops, t)

    label_w = 7 if show_axis else 0
    lines: list[str] = []

    if title:
        lines.append(f"{'':>{label_w}}  {title}")

    for row in range(height):
        row_val = mx - (row / max(height - 1, 1)) * val_range

        if show_axis and row in (0, height // 2, height - 1):
            label = _format_label(row_val, label_w)
        elif show_axis:
            label = " " * label_w
        else:
            label = ""

        border = " \u2524" if show_axis else ""

        # Build a cell grid — last series to draw wins
        cells: list[str] = [" "] * width
        for name in names:
            data = resampled[name]
            color = series_colors[name]
            for col in range(width):
                data_row = (mx - data[col]) / val_range * (height - 1)
                if abs(row - data_row) < 0.6:
                    if has_color and bg_fn:
                        cells[col] = f"{bg_fn(*color)} "
                    else:
                        cells[col] = "*"

        row_str = "".join(cells)
        if has_color:
            row_str += _BG_RESET
        lines.append(f"{label}{border}{row_str}")

    if show_axis:
        lines.append(f"{'':>{label_w}} \u2514{'─' * width}")

    # Legend
    if has_color and fg_fn:
        legend_parts = []
        for name in names:
            c = series_colors[name]
            legend_parts.append(f"  {bg_fn(*c)}  {_BG_RESET} {name}")
        lines.append("".join(legend_parts))

    return "\n".join(lines)


# ─── Chug Chart ───────────────────────────────────────────────────────────────

def bar_chart(
    data: dict[str, float],
    width: int = 40,
    gradient: str = "ocean",
    show_values: bool = True,
) -> str:
    """Render a horizontal bar chart.

    Each key-value pair becomes a labeled horizontal bar. The gradient
    is applied along each bar's length.

    Args:
        data: Dict of {label: value}.
        width: Maximum bar width in characters.
        gradient: Gradient preset name.
        show_values: Show numeric values after each bar.

    Returns:
        Multi-line string ready to print.
    """
    if not data:
        return ""

    bg_fn, fg_fn, has_color = _get_color_fns()
    stops = get_gradient(gradient)

    mx = max(data.values())
    if mx == 0:
        mx = 1.0

    # Label width = longest label + padding
    label_w = max(len(k) for k in data) + 2

    lines: list[str] = []
    for label, value in data.items():
        bar_len = int((value / mx) * width)
        bar_len = max(1, bar_len) if value > 0 else 0

        # Gradient bar
        chars: list[str] = []
        for i in range(bar_len):
            t = i / max(bar_len - 1, 1)
            color = _lerp_multi(stops, t)
            if has_color and bg_fn:
                chars.append(f"{bg_fn(*color)} ")
            else:
                chars.append("=")
        bar_str = "".join(chars)
        if has_color:
            bar_str += _BG_RESET

        # Value label
        val_str = f" {value:g}" if show_values else ""

        lines.append(f"  {label:>{label_w}} {bar_str}{val_str}")

    return "\n".join(lines)


# ─── Heatmap ─────────────────────────────────────────────────────────────────

def heatmap(
    matrix: list[list[float]],
    gradient: str = "fire",
    labels: list[str] | None = None,
    cell_width: int = 6,
    title: str = "",
) -> str:
    """Render a heatmap / matrix visualization.

    Each cell is colored based on its value, interpolated through the
    gradient from min (start color) to max (end color).

    Args:
        matrix: 2D list of values.
        gradient: Gradient preset name.
        labels: Row/column labels (same for both if square).
        cell_width: Width of each cell in characters.
        title: Optional title.

    Returns:
        Multi-line string ready to print.
    """
    if not matrix or not matrix[0]:
        return ""

    bg_fn, fg_fn, has_color = _get_color_fns()
    stops = get_gradient(gradient)

    rows = len(matrix)
    cols = len(matrix[0])

    # Find value range
    all_vals = [v for row in matrix for v in row]
    mn, mx = min(all_vals), max(all_vals)
    if mn == mx:
        mx = mn + 1.0

    # Labels
    if labels is None:
        labels = [str(i) for i in range(max(rows, cols))]
    label_w = max(len(l) for l in labels) + 2

    lines: list[str] = []
    if title:
        lines.append(f"{'':>{label_w}}  {title}")

    # Column headers
    header = " " * (label_w + 1)
    for c in range(cols):
        lbl = labels[c] if c < len(labels) else str(c)
        header += lbl.center(cell_width)
    lines.append(header)

    # Data rows
    for r in range(rows):
        row_label = labels[r] if r < len(labels) else str(r)
        row_label = row_label.rjust(label_w)

        chars: list[str] = []
        for c in range(cols):
            val = matrix[r][c]
            t = (val - mn) / (mx - mn)
            color = _lerp_multi(stops, t)

            # Cell: cell_width background-colored spaces
            if has_color and bg_fn:
                cell = f"{bg_fn(*color)}{' ' * cell_width}{_BG_RESET}"
            else:
                # ASCII fallback
                blocks = " ░▒▓█"
                idx = int(t * (len(blocks) - 1))
                cell = blocks[idx] * cell_width

            chars.append(cell)

        lines.append(f"{row_label} {''.join(chars)}")

    # Value range legend
    if has_color and bg_fn:
        legend_chars = []
        legend_w = min(30, cols * cell_width)
        for i in range(legend_w):
            t = i / max(legend_w - 1, 1)
            color = _lerp_multi(stops, t)
            legend_chars.append(f"{bg_fn(*color)} ")
        legend = "".join(legend_chars) + _BG_RESET
        lines.append(f"{'':>{label_w}} {_format_label(mn, 5)} {legend} {_format_label(mx, 5)}")

    return "\n".join(lines)


# ─── Scatter Plot ────────────────────────────────────────────────────────────

def scatter(
    x: list[float],
    y: list[float],
    width: int = 60,
    height: int = 15,
    gradient: str = "cyber",
    title: str = "",
    show_axis: bool = True,
) -> str:
    """Render a scatter plot using background-colored spaces.

    Points are mapped to character cells. When multiple points land in
    the same cell, the color intensifies (density-based).

    Args:
        x: X-coordinates.
        y: Y-coordinates.
        width: Chart width.
        height: Chart height.
        gradient: Gradient preset.
        title: Optional title.
        show_axis: Show axis labels.

    Returns:
        Multi-line string ready to print.
    """
    if not x or not y or len(x) != len(y):
        return ""

    bg_fn, fg_fn, has_color = _get_color_fns()
    stops = get_gradient(gradient)

    x_mn, x_mx = min(x), max(x)
    y_mn, y_mx = min(y), max(y)
    if x_mn == x_mx:
        x_mx = x_mn + 1.0
    if y_mn == y_mx:
        y_mx = y_mn + 1.0

    # Build density grid
    grid: list[list[int]] = [[0] * width for _ in range(height)]
    for xi, yi in zip(x, y):
        col = int((xi - x_mn) / (x_mx - x_mn) * (width - 1))
        row = int((1.0 - (yi - y_mn) / (y_mx - y_mn)) * (height - 1))
        col = max(0, min(width - 1, col))
        row = max(0, min(height - 1, row))
        grid[row][col] += 1

    max_density = max(v for row in grid for v in row)
    if max_density == 0:
        max_density = 1

    label_w = 7 if show_axis else 0
    lines: list[str] = []

    if title:
        lines.append(f"{'':>{label_w}}  {title}")

    for row in range(height):
        row_val = y_mx - (row / max(height - 1, 1)) * (y_mx - y_mn)

        if show_axis and row in (0, height // 2, height - 1):
            label = _format_label(row_val, label_w)
        elif show_axis:
            label = " " * label_w
        else:
            label = ""

        border = " \u2524" if show_axis else ""

        chars: list[str] = []
        for col in range(width):
            density = grid[row][col]
            if density > 0:
                t = density / max_density
                color = _lerp_multi(stops, min(t * 2, 1.0))
                color = _brighten(color, t * 0.3)
                if has_color and bg_fn:
                    chars.append(f"{bg_fn(*color)} ")
                else:
                    chars.append("*")
            else:
                chars.append(" ")

        row_str = "".join(chars)
        if has_color:
            row_str += _BG_RESET
        lines.append(f"{label}{border}{row_str}")

    if show_axis:
        lines.append(f"{'':>{label_w}} \u2514{'─' * width}")
        # X-axis labels
        x_min_label = _format_label(x_mn, 6)
        x_max_label = _format_label(x_mx, 6)
        x_mid_label = _format_label((x_mn + x_mx) / 2, 6)
        pad = width - len(x_min_label) - len(x_max_label) - len(x_mid_label)
        left_pad = pad // 2
        right_pad = pad - left_pad
        lines.append(
            f"{'':>{label_w}}  {x_min_label}{' ' * left_pad}{x_mid_label}"
            f"{' ' * right_pad}{x_max_label}"
        )

    return "\n".join(lines)
