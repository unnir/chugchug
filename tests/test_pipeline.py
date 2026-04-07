"""Tests for _pipeline.py — DAG validation, bottleneck detection."""

import time

import pytest

from chugchug._pipeline import Pipeline
from chugchug._tracker import Registry


class TestPipelineValidation:
    def test_simple_linear(self):
        pipe = Pipeline()
        pipe.add_stage("a", total=100)
        pipe.add_stage("b", total=100, depends_on=["a"])
        pipe.add_stage("c", total=100, depends_on=["b"])

        order = pipe.validate()
        assert order == ["a", "b", "c"]

    def test_diamond(self):
        pipe = Pipeline()
        pipe.add_stage("a", total=100)
        pipe.add_stage("b", total=100, depends_on=["a"])
        pipe.add_stage("c", total=100, depends_on=["a"])
        pipe.add_stage("d", total=100, depends_on=["b", "c"])

        order = pipe.validate()
        assert order[0] == "a"
        assert order[-1] == "d"
        assert set(order[1:3]) == {"b", "c"}

    def test_cycle_detection(self):
        pipe = Pipeline()
        pipe.add_stage("a", depends_on=["c"])
        pipe.add_stage("b", depends_on=["a"])
        pipe.add_stage("c", depends_on=["b"])

        with pytest.raises(ValueError, match="cycle"):
            pipe.validate()

    def test_unknown_dependency(self):
        pipe = Pipeline()
        pipe.add_stage("a", depends_on=["nonexistent"])

        with pytest.raises(ValueError, match="unknown stage"):
            pipe.validate()

    def test_no_stages(self):
        pipe = Pipeline()
        order = pipe.validate()
        assert order == []

    def test_single_stage(self):
        pipe = Pipeline()
        pipe.add_stage("only")
        order = pipe.validate()
        assert order == ["only"]


class TestPipelineStages:
    def test_stage_returns_tracker(self):
        reg = Registry()
        pipe = Pipeline(registry=reg)
        pipe.add_stage("extract", total=100, desc="Extracting")

        tracker = pipe.stage("extract")
        assert tracker.name == "pipeline/extract"
        assert tracker.total == 100

    def test_unknown_stage(self):
        pipe = Pipeline()
        pipe.add_stage("a")
        pipe.validate()

        with pytest.raises(KeyError):
            pipe.stage("nonexistent")

    def test_chaining(self):
        pipe = Pipeline()
        result = pipe.add_stage("a").add_stage("b").add_stage("c")
        assert result is pipe


class TestPipelineProgress:
    def test_overall_progress(self):
        reg = Registry()
        pipe = Pipeline(registry=reg)
        pipe.add_stage("a", total=100)
        pipe.add_stage("b", total=100)

        assert pipe.overall_progress() == 0.0

        t = pipe.stage("a")
        t._n = 50  # Directly set for testing
        assert 0.2 < pipe.overall_progress() < 0.3

    def test_critical_path_linear(self):
        reg = Registry()
        pipe = Pipeline(registry=reg)
        pipe.add_stage("a", total=100)
        pipe.add_stage("b", total=100, depends_on=["a"])

        # Start stages so they have trackers
        pipe.stage("a")
        pipe.stage("b")

        path = pipe.critical_path()
        assert "a" in path or "b" in path

    def test_context_manager(self):
        reg = Registry()
        pipe = Pipeline(registry=reg)
        pipe.add_stage("a", total=10)

        with pipe:
            t = pipe.stage("a")
            for _ in range(10):
                t.update()

    def test_bottleneck(self):
        reg = Registry()
        pipe = Pipeline(registry=reg)
        pipe.add_stage("fast", total=100)
        pipe.add_stage("slow", total=100, depends_on=["fast"])

        fast = pipe.stage("fast")
        slow = pipe.stage("slow")

        # Simulate fast completing quickly, slow being slower
        for _ in range(100):
            fast.update()
        pipe.mark_complete("fast")

        for _ in range(10):
            slow.update()
        time.sleep(0.1)

        bottleneck = pipe.bottleneck()
        assert bottleneck == "slow"
