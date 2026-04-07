"""Pure formatting functions — no side effects, no state."""

from __future__ import annotations


def format_time(seconds: float | None) -> str:
    """Format seconds into human-readable time string."""
    if seconds is None or seconds < 0:
        return "??:??"
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}:{s:02d}"
    h, remainder = divmod(int(seconds), 3600)
    m, s = divmod(remainder, 60)
    return f"{h}:{m:02d}:{s:02d}"


def format_rate(rate: float | None, unit: str = "it", unit_scale: bool = False) -> str:
    """Format iteration rate."""
    if rate is None:
        return f"? {unit}/s"
    if unit_scale:
        if rate >= 1e9:
            return f"{rate / 1e9:.2f}G{unit}/s"
        if rate >= 1e6:
            return f"{rate / 1e6:.2f}M{unit}/s"
        if rate >= 1e3:
            return f"{rate / 1e3:.2f}K{unit}/s"
    if rate >= 100:
        return f"{rate:.0f}{unit}/s"
    if rate >= 1:
        return f"{rate:.1f}{unit}/s"
    return f"{rate:.2f}{unit}/s"


def format_count(n: int, total: int | None = None, unit_scale: bool = False) -> str:
    """Format count with optional scaling."""
    def _fmt(x: int) -> str:
        if not unit_scale:
            return str(x)
        if x >= 1e9:
            return f"{x / 1e9:.1f}G"
        if x >= 1e6:
            return f"{x / 1e6:.1f}M"
        if x >= 1e3:
            return f"{x / 1e3:.1f}K"
        return str(x)

    if total is not None:
        return f"{_fmt(n)}/{_fmt(total)}"
    return _fmt(n)


def format_bytes(n: int) -> str:
    """Format byte count into human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            if unit == "B":
                return f"{n}{unit}"
            return f"{n:.1f}{unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f}PB"
