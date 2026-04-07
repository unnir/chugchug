"""CLI: python -m chugchug — pipe mode, watch, replay."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from ._bar import Chug
from ._persistence import TimeSeriesHandler
from ._types import OutputMode


def cmd_pipe(args: argparse.Namespace) -> None:
    """Pipe mode: wrap stdin line-by-line with a progress bar."""
    total = args.total
    bar = Chug(
        total=total,
        desc=args.desc or "pipe",
        unit=args.unit or "line",
        gradient=args.gradient or "ocean",
    )

    try:
        for line in sys.stdin:
            sys.stdout.write(line)
            sys.stdout.flush()
            bar.update()
    except KeyboardInterrupt:
        pass
    finally:
        bar.close()


def cmd_watch(args: argparse.Namespace) -> None:
    """Watch mode: display progress from a JSONL file in real-time."""
    path = Path(args.file)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)

    bar = Chug(desc="Watching", unit="event")
    try:
        with open(path) as f:
            # Seek to end
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    bar.update()
                else:
                    time.sleep(0.1)
    except KeyboardInterrupt:
        bar.close()


def cmd_replay(args: argparse.Namespace) -> None:
    """Replay mode: replay a JSONL time series."""
    path = Path(args.file)
    ts = TimeSeriesHandler(path)
    records = ts.read()

    if not records:
        print("No records to replay.", file=sys.stderr)
        return

    speed = args.speed or 1.0
    bar = Chug(
        total=len(records),
        desc="Replaying",
        gradient=args.gradient or "cyber",
    )

    last_t = records[0].get("t", 0)
    for record in records:
        t = record.get("t", 0)
        delay = (t - last_t) / speed
        if delay > 0:
            time.sleep(min(delay, 1.0))
        last_t = t
        bar.update()
    bar.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="chugchug",
        description="chugchug — next-generation progress bars",
    )
    sub = parser.add_subparsers(dest="command")

    # pipe
    p_pipe = sub.add_parser("pipe", help="Wrap stdin with a progress bar")
    p_pipe.add_argument("--total", "-n", type=int, default=None)
    p_pipe.add_argument("--desc", "-d", type=str, default=None)
    p_pipe.add_argument("--unit", "-u", type=str, default=None)
    p_pipe.add_argument("--gradient", "-g", type=str, default=None)

    # watch
    p_watch = sub.add_parser("watch", help="Watch a JSONL file for progress")
    p_watch.add_argument("file", type=str)

    # replay
    p_replay = sub.add_parser("replay", help="Replay a JSONL time series")
    p_replay.add_argument("file", type=str)
    p_replay.add_argument("--speed", "-s", type=float, default=1.0)
    p_replay.add_argument("--gradient", "-g", type=str, default=None)

    args = parser.parse_args()

    if args.command == "pipe":
        cmd_pipe(args)
    elif args.command == "watch":
        cmd_watch(args)
    elif args.command == "replay":
        cmd_replay(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
