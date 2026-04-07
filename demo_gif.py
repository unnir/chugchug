#!/usr/bin/env python3
"""
chugchug GIF demo — optimized for terminal recording (~20s).

Record:  asciinema rec -c "python demo_gif.py" demo.cast
Run:     python demo_gif.py
"""

import math
import random
import time

from chugchug import Chug, chug


def p(text: str = "") -> None:
    print(f"  \033[2m{text}\033[0m" if text else "")


def code(text: str) -> None:
    """Show code snippet."""
    print(f"  \033[33m>>>\033[0m \033[97m{text}\033[0m")


def section(pause: float = 0.4) -> None:
    print()
    time.sleep(pause)


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # ── Intro ──
    print()
    print("  \033[1;97mchugchug\033[0m \033[2m— progress bars that don't suck\033[0m")
    section(1.0)

    # ── 1. Basic — show code then result ──
    code("for x in chug(data, desc='Loading'):")
    code("    process(x)")
    section(0.3)

    for _ in chug(range(100), desc="Loading", gradient="ocean", min_interval=0.02):
        time.sleep(0.008)
    section()

    # ── 2. Pick your gradient ──
    code("chug(data, gradient='fire')")
    section(0.3)

    for g in ["fire", "cyber", "rainbow", "aurora", "candy"]:
        for _ in chug(range(50), desc=f" {g:7s}", gradient=g, min_interval=0.02):
            time.sleep(0.004)
    section()

    # ── 3. ML training with metrics ──
    code("b.set_metrics(loss=..., acc=...)")
    section(0.3)

    b = Chug(total=60, desc=" Training", gradient="fire", unit="step")
    for step in range(60):
        loss = 2.5 * math.exp(-step / 15) + random.gauss(0, 0.03)
        acc = min(99.0, 50 + 49 * (1 - math.exp(-step / 12)))
        b.set_metrics(loss=f"{loss:.3f}", acc=f"{acc:.1f}%")
        b.update()
        time.sleep(0.035)
    b.close()
    section()

    # ── 4. Smart wrapping — tqdm can't do this ──
    code("chug(map(fn, data))  # tqdm shows '?', we show the bar")
    section(0.3)

    data = list(range(120))
    for _ in chug(map(str, data), desc=" map()", gradient="purple", min_interval=0.02):
        time.sleep(0.004)
    section()

    # ── 5. Pipeline ──
    code("# multi-stage pipelines")
    section(0.3)

    for name, g in [("Extract", "ocean"), ("Transform", "fire"), ("Load", "cyber")]:
        for _ in chug(range(50), desc=f" {name:10s}", gradient=g, min_interval=0.02):
            time.sleep(0.004)
    section()

    # ── Outro — gradient banner ──
    print()
    # Build a gradient-colored banner using background colors
    from chugchug._gradient import _lerp_multi, get_gradient
    import shutil
    cols = min(shutil.get_terminal_size().columns - 4, 120)
    stops = get_gradient("rainbow")

    # Top bar
    top = ""
    for i in range(cols):
        r, g, b = _lerp_multi(stops, i / max(cols - 1, 1))
        top += f"\033[48;2;{r};{g};{b}m "
    print(f"  {top}\033[0m")

    # Content lines with gradient left border
    def banner_line(text: str = "") -> None:
        r, g, b = _lerp_multi(stops, 0.0)
        r2, g2, b2 = _lerp_multi(stops, 0.15)
        border = f"\033[48;2;{r};{g};{b}m \033[48;2;{r2};{g2};{b2}m \033[0m"
        print(f"  {border} {text}")

    banner_line()
    banner_line("\033[1;97mpip install chugchug\033[0m")
    banner_line()
    banner_line("\033[2mfrom chugchug import chug\033[0m")
    banner_line("\033[2mfor x in chug(data): process(x)\033[0m")
    banner_line()
    banner_line("\033[2m14 gradients  |  smart ETA  |  zero deps\033[0m")
    banner_line("\033[2mML metrics   |  pipelines  |  notebooks\033[0m")
    banner_line()

    # Bottom bar
    bot = ""
    for i in range(cols):
        r, g, b = _lerp_multi(stops, i / max(cols - 1, 1))
        bot += f"\033[48;2;{r};{g};{b}m "
    print(f"  {bot}\033[0m")
    print()
    time.sleep(3)
