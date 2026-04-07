"""Pipeline/DAG progress — multi-stage with bottleneck detection.

Define stages with dependencies, get composite progress display
with critical path computation and bottleneck markers.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from ._tracker import Registry, Tracker, get_registry
from ._types import HandlerProtocol, ProgressEvent, TrackerState


@dataclass
class Stage:
    """A single stage in a pipeline."""
    name: str
    total: int | None = None
    desc: str = ""
    depends_on: list[str] = field(default_factory=list)
    # Computed at runtime
    tracker: Tracker | None = None
    start_time: float | None = None
    end_time: float | None = None


class Pipeline:
    """Multi-stage progress pipeline with DAG validation.

    Usage:
        pipe = Pipeline("ETL")
        pipe.add_stage("extract", total=1000, desc="Extracting")
        pipe.add_stage("transform", total=1000, desc="Transforming", depends_on=["extract"])
        pipe.add_stage("load", total=1000, desc="Loading", depends_on=["transform"])

        with pipe:
            ext = pipe.stage("extract")
            for i in range(1000):
                ext.update()
            ext.close()
            ...
    """

    def __init__(self, name: str = "pipeline", registry: Registry | None = None) -> None:
        self._name = name
        self._stages: dict[str, Stage] = {}
        self._order: list[str] = []
        self._registry = registry or get_registry()
        self._validated = False

    def add_stage(
        self,
        name: str,
        total: int | None = None,
        desc: str = "",
        depends_on: list[str] | None = None,
    ) -> Pipeline:
        """Add a stage to the pipeline. Returns self for chaining."""
        self._stages[name] = Stage(
            name=name,
            total=total,
            desc=desc or name,
            depends_on=depends_on or [],
        )
        self._validated = False
        return self

    def validate(self) -> list[str]:
        """Validate the DAG using Kahn's algorithm. Returns topological order.

        Raises ValueError if cycles are detected.
        """
        in_degree: dict[str, int] = {name: 0 for name in self._stages}
        adjacency: dict[str, list[str]] = defaultdict(list)

        for name, stage in self._stages.items():
            for dep in stage.depends_on:
                if dep not in self._stages:
                    raise ValueError(f"Stage '{name}' depends on unknown stage '{dep}'")
                adjacency[dep].append(name)
                in_degree[name] += 1

        queue: deque[str] = deque()
        for name, deg in in_degree.items():
            if deg == 0:
                queue.append(name)

        order: list[str] = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in adjacency[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self._stages):
            raise ValueError("Pipeline contains a cycle")

        self._order = order
        self._validated = True
        return order

    def stage(self, name: str) -> Tracker:
        """Get a tracker for a stage. The tracker is wired to the pipeline's registry."""
        if not self._validated:
            self.validate()

        if name not in self._stages:
            raise KeyError(f"Unknown stage: {name}")

        s = self._stages[name]
        if s.tracker is None:
            tracker_name = f"{self._name}/{name}"
            s.tracker = self._registry.get_tracker(
                tracker_name,
                total=s.total,
                desc=s.desc,
                parent=self._name,
            )
            s.start_time = time.monotonic()

        return s.tracker

    def critical_path(self) -> list[str]:
        """Compute the critical path (longest remaining time path).

        Uses estimated remaining time based on current progress rates.
        """
        if not self._validated:
            self.validate()

        # Estimate remaining time for each stage
        remaining: dict[str, float] = {}
        for name, stage in self._stages.items():
            if stage.end_time is not None:
                remaining[name] = 0.0
            elif stage.tracker is not None and stage.total and stage.total > 0:
                elapsed = time.monotonic() - (stage.start_time or time.monotonic())
                n = stage.tracker.n
                if n > 0:
                    rate = n / elapsed
                    remaining[name] = (stage.total - n) / rate
                else:
                    remaining[name] = float("inf")
            else:
                remaining[name] = float("inf")

        # Longest path via dynamic programming on topological order
        dist: dict[str, float] = {name: 0.0 for name in self._stages}
        parent_map: dict[str, str | None] = {name: None for name in self._stages}

        for name in self._order:
            stage = self._stages[name]
            for dep in stage.depends_on:
                if dist[dep] + remaining[dep] > dist[name]:
                    dist[name] = dist[dep] + remaining[dep]
                    parent_map[name] = dep

        # Find the end node with maximum distance + own remaining
        end_node = max(self._stages, key=lambda n: dist[n] + remaining[n])

        # Trace back
        path: list[str] = [end_node]
        current = parent_map[end_node]
        while current is not None:
            path.append(current)
            current = parent_map[current]
        path.reverse()
        return path

    def bottleneck(self) -> str | None:
        """Identify the bottleneck — lowest throughput on the critical path."""
        path = self.critical_path()
        if not path:
            return None

        min_rate = float("inf")
        bottleneck_stage = None

        for name in path:
            stage = self._stages[name]
            if stage.tracker is None or stage.end_time is not None:
                continue
            if stage.start_time is None:
                continue
            elapsed = time.monotonic() - stage.start_time
            n = stage.tracker.n
            if elapsed > 0 and n > 0:
                rate = n / elapsed
                if rate < min_rate:
                    min_rate = rate
                    bottleneck_stage = name

        return bottleneck_stage

    def overall_progress(self) -> float:
        """Compute overall pipeline progress (0.0 to 1.0)."""
        if not self._stages:
            return 0.0

        total_weight = 0
        completed_weight = 0.0

        for stage in self._stages.values():
            weight = stage.total or 1
            total_weight += weight
            if stage.tracker is not None:
                if stage.total and stage.total > 0:
                    completed_weight += weight * min(stage.tracker.n / stage.total, 1.0)
                elif stage.end_time is not None:
                    completed_weight += weight

        return completed_weight / total_weight if total_weight > 0 else 0.0

    def mark_complete(self, name: str) -> None:
        """Mark a stage as complete."""
        if name in self._stages:
            self._stages[name].end_time = time.monotonic()

    def __enter__(self) -> Pipeline:
        if not self._validated:
            self.validate()
        return self

    def __exit__(self, *args: Any) -> None:
        # Close any remaining trackers
        for stage in self._stages.values():
            if stage.tracker is not None and stage.end_time is None:
                stage.tracker.close()
                stage.end_time = time.monotonic()
