#!/usr/bin/env python3
"""
chugchug Demo — Showcasing next-generation progress bars.
Run: python demo.py
"""

import io
import math
import random
import time

from chugchug import (
    Chug, chug, OutputMode, register_gradient, register_multi_gradient,
)
from chugchug._training import TrainingChug
from chugchug._pipeline import Pipeline
from chugchug._tracker import Registry


def demo_basic():
    """1. Basic usage — drop-in replacement with gradient bar."""
    print("\n" + "=" * 56)
    print("  1. BASIC USAGE -- Beautiful gradient by default")
    print("=" * 56 + "\n")

    for _ in chug(range(200), desc="Processing"):
        time.sleep(0.01)
    print()


def demo_gradients():
    """2. Built-in gradient presets."""
    print("\n" + "=" * 56)
    print("  2. GRADIENT PRESETS -- Now with multi-stop gradients")
    print("=" * 56 + "\n")

    gradients = [
        "ocean", "fire", "forest", "purple", "cyber", "mono",
        "rainbow", "heatmap", "candy", "neon", "aurora", "sunset",
        "matrix", "ice",
    ]
    for g in gradients:
        for _ in chug(range(100), desc=f"{g:8s}", gradient=g, min_interval=0.02):
            time.sleep(0.003)
        print()


def demo_smart_eta():
    """3. Smart ETA — handles variable-speed tasks."""
    print("\n" + "=" * 56)
    print("  3. SMART ETA -- Adapts to speed changes")
    print("=" * 56 + "\n")

    print("  (Notice ETA adjusts as speed varies)\n")
    b = Chug(total=100, desc="Variable speed", gradient="cyber")
    for i in range(100):
        delay = 0.01 + 0.04 * math.sin(i / 10) ** 2
        time.sleep(delay)
        b.update()
    b.close()
    print()


def demo_metrics():
    """4. ML-style metrics — show loss, lr, accuracy inline."""
    print("\n" + "=" * 56)
    print("  4. ML METRICS -- Built-in loss/accuracy display")
    print("=" * 56 + "\n")

    b = Chug(total=50, desc="Training", gradient="fire", unit="step")
    for step in range(50):
        loss = 2.5 * math.exp(-step / 15) + random.gauss(0, 0.05)
        acc = min(0.99, 0.5 + 0.5 * (1 - math.exp(-step / 12)))
        lr = 0.001 * (0.95 ** step)

        b.set_metrics(
            loss=f"{loss:.4f}",
            acc=f"{acc:.2%}",
            lr=f"{lr:.2e}",
        )
        b.update()
        time.sleep(0.08)
    b.close()
    print()


def demo_spinner():
    """5. Spinner mode — unknown total."""
    print("\n" + "=" * 56)
    print("  5. SPINNER MODE -- Color-cycling spinner")
    print("=" * 56 + "\n")

    b = Chug(desc="Streaming data", unit="rec", gradient="rainbow")
    for i in range(80):
        b.update()
        time.sleep(0.03)
    b.close()
    print()


def demo_json_output():
    """7. JSON output — structured logging for CI/CD."""
    print("\n" + "=" * 56)
    print("  7. JSON OUTPUT -- For CI/CD & cloud logging")
    print("=" * 56 + "\n")

    buf = io.StringIO()
    b = Chug(
        total=5,
        desc="Pipeline",
        output=OutputMode.JSON,
        file=buf,
        min_interval=0,
    )
    for i in range(5):
        b.set_metrics(stage=f"step_{i}")
        b.update()
    b.close()

    print("  Structured output (each update is a JSON line):")
    for line in buf.getvalue().strip().split("\n")[:3]:
        print(f"    {line}")
    print(f"    ... ({buf.getvalue().count(chr(10))} total lines)")
    print()


def demo_early_complete():
    """8. Early completion — clean exit with green flash."""
    print("\n" + "=" * 56)
    print("  8. EARLY COMPLETION -- Clean break with completion flash")
    print("=" * 56 + "\n")

    b = Chug(total=1000, desc="Searching", gradient="purple")
    for i in range(1000):
        time.sleep(0.002)
        b.update()
        if i == 237:
            b.set_metrics(found="item_237")
            b.complete()
            break
    print()


def demo_unit_scale():
    """9. Unit scaling — human-readable large numbers."""
    print("\n" + "=" * 56)
    print("  9. UNIT SCALING -- Human-readable numbers")
    print("=" * 56 + "\n")

    b = Chug(
        total=1_000_000,
        desc="Tokens",
        unit="tok",
        unit_scale=True,
        gradient="ocean",
        min_interval=0.02,
    )
    for _ in range(100):
        b.update(10000)
        time.sleep(0.03)
    b.close()
    print()


def demo_training_bar():
    """10. TrainingChug — purpose-built for ML."""
    print("\n" + "=" * 56)
    print("  10. TRAINING BAR -- Purpose-built for ML loops")
    print("=" * 56 + "\n")

    data = list(range(30))
    tracker = TrainingChug(epochs=3, steps_per_epoch=len(data))

    for epoch in tracker.epochs():
        for batch in tracker.steps(data):
            loss = 2.0 * math.exp(-epoch * 0.5) + random.gauss(0, 0.1)
            tracker.log(loss=loss, epoch=epoch + 1)
            time.sleep(0.02)
    print()


def demo_ascii_fallback():
    """11. ASCII fallback — works everywhere."""
    print("\n" + "=" * 56)
    print("  11. ASCII MODE -- Works in any terminal")
    print("=" * 56 + "\n")

    for _ in chug(range(100), desc="ASCII mode", ascii=True):
        time.sleep(0.01)
    print()


def demo_pipeline():
    """12. Pipeline progress — multi-stage with bottleneck detection."""
    print("\n" + "=" * 56)
    print("  12. PIPELINE -- Multi-stage DAG progress")
    print("=" * 56 + "\n")

    reg = Registry()
    pipe = Pipeline("ETL", registry=reg)
    pipe.add_stage("extract", total=50, desc="Extracting")
    pipe.add_stage("transform", total=50, desc="Transforming", depends_on=["extract"])
    pipe.add_stage("load", total=50, desc="Loading", depends_on=["transform"])

    with pipe:
        for name in ["extract", "transform", "load"]:
            print(f"  Stage: {name}")
            stage = pipe.stage(name)
            for _ in range(50):
                stage.update()
                time.sleep(0.01)
            stage.close()
            pipe.mark_complete(name)

    overall = pipe.overall_progress()
    print(f"\n  Overall pipeline progress: {overall:.0%}")
    print()


def demo_tqdm_compat():
    """13. tqdm drop-in compatibility."""
    print("\n" + "=" * 56)
    print("  13. TQDM COMPAT -- Drop-in replacement")
    print("=" * 56 + "\n")

    from chugchug.compat import tqdm, trange

    for _ in tqdm(range(100), desc="tqdm compat"):
        time.sleep(0.01)
    print()


def demo_custom_gradient():
    """14. Custom gradient registration — 2-stop and multi-stop."""
    print("\n" + "=" * 56)
    print("  14. CUSTOM GRADIENTS -- Register your own colors")
    print("=" * 56 + "\n")

    # Classic 2-stop
    register_gradient("coral", (255, 94, 77), (255, 195, 113))
    for _ in chug(range(100), desc="Coral   ", gradient="coral"):
        time.sleep(0.008)
    print()

    # Multi-stop custom gradient
    register_multi_gradient("vaporwave", [
        (255, 0, 128), (128, 0, 255), (0, 200, 255),
        (128, 255, 128), (255, 255, 0), (255, 0, 128),
    ])
    for _ in chug(range(100), desc="Vapor   ", gradient="vaporwave"):
        time.sleep(0.008)
    print()

    register_multi_gradient("ocean_deep", [
        (0, 10, 40), (0, 60, 120), (0, 140, 200),
        (60, 220, 220), (180, 255, 255),
    ])
    for _ in chug(range(100), desc="Deep Sea", gradient="ocean_deep"):
        time.sleep(0.008)
    print()


def demo_smart_generators():
    """15. Smart generator wrapping -- tqdm shows nothing, chugchug shows a real bar."""
    print("\n" + "=" * 56)
    print("  15. SMART GENERATORS -- tqdm fails, chugchug works")
    print("=" * 56 + "\n")

    data = list(range(200))
    print("  chug(map(fn, list)) -- extracts total from map():")
    for _ in chug(map(str, data), desc="map()", min_interval=0.02):
        time.sleep(0.005)
    print()

    print("  chug(enumerate(list)) -- extracts total from enumerate():")
    for _ in chug(enumerate(data), desc="enumerate()", min_interval=0.02):
        time.sleep(0.005)
    print()

    print("  chug(x**2 for x in list) -- extracts total from genexpr:")
    for _ in chug((x**2 for x in data), desc="genexpr", min_interval=0.02):
        time.sleep(0.005)
    print()


def demo_crash_context():
    """16. Exception context -- rich crash info when things go wrong."""
    print("\n" + "=" * 56)
    print("  16. CRASH CONTEXT -- Know exactly where it died")
    print("=" * 56 + "\n")

    print("  Simulating a crash at iteration 42:")
    try:
        with Chug(range(100), desc="Processing", gradient="fire") as b:
            for i in b:
                if i == 42:
                    raise ValueError("data corrupted at row 42")
                time.sleep(0.01)
    except ValueError:
        pass
    print()


def demo_rainbow_showcase():
    """17. Multi-gradient showcase — all new presets side by side."""
    print("\n" + "=" * 56)
    print("  17. GRADIENT SHOWCASE -- The full rainbow experience")
    print("=" * 56 + "\n")

    # Show all bars at different completion levels
    for pct, g in [
        (100, "rainbow"), (85, "aurora"), (70, "neon"),
        (55, "candy"), (45, "sunset"), (30, "matrix"),
        (60, "heatmap"), (90, "ice"),
    ]:
        b = Chug(total=100, desc=f"{g:8s}", gradient=g, min_interval=0.01)
        for i in range(pct):
            b.update()
            time.sleep(0.005)
        b.close()
        print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("   CHUGCHUG -- Next-Generation Progress Bars & Viz")
    print("   Event-driven. Multiprocessing-safe. Pipeline-aware.")
    print("=" * 60)

    demos = [
        demo_basic,
        demo_gradients,
        demo_smart_eta,
        demo_metrics,
        demo_spinner,
        demo_json_output,
        demo_early_complete,
        demo_unit_scale,
        demo_training_bar,
        demo_ascii_fallback,
        demo_pipeline,
        demo_tqdm_compat,
        demo_custom_gradient,
        demo_smart_generators,
        demo_crash_context,
        demo_rainbow_showcase,
    ]

    for demo_fn in demos:
        demo_fn()

    print("\n" + "=" * 60)
    print("  All demos complete!")
    print("  Key features:")
    print("    - Beautiful gradient bars (background-color technique)")
    print("    - Multi-stop gradients (rainbow, aurora, neon, ...)")
    print("    - Auto-colored metrics (green=improving, red=worsening)")
    print("    - Completion summary (avg/peak speed)")
    print("    - Smart ETA (regression + exponential ensemble)")
    print("    - Event-driven architecture")
    print("    - Multiprocessing that actually works (spawn-safe)")
    print("    - Pipeline/DAG progress with bottleneck detection")
    print("    - tqdm drop-in compatibility")
    print("    - Zero dependencies")
    print("=" * 60 + "\n")
