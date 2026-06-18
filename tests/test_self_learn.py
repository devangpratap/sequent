"""Tests for verifier/self_learn.py — ExperienceStore, collect_experience, OnlineLearner."""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verifier.self_learn import Experience, ExperienceStore, OnlineLearner, collect_experience
from verifier.neurosymbolic import (
    GNNPrediction,
    SequentEngine,
    SequentResult,
)
from verifier.z3_engine import PropertyCheck, VerificationReport, VerificationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_experience(code: str = "def foo(): pass", function_name: str = "foo",
                     is_buggy: bool = False, z3_label: int = 0,
                     gnn_confidence: float = 0.9, gnn_was_correct: bool = True,
                     bug_lines: list | None = None, property_name: str = "") -> Experience:
    return Experience(
        code=code,
        function_name=function_name,
        is_buggy=is_buggy,
        z3_label=z3_label,
        gnn_confidence=gnn_confidence,
        gnn_was_correct=gnn_was_correct,
        bug_lines=bug_lines or [],
        property_name=property_name,
    )


SIMPLE_CODE = """\
def add(a, b):
    return a + b
"""

BUGGY_CODE = """\
def divide(a, b):
    return a / b
"""


# ---------------------------------------------------------------------------
# TestExperienceStore
# ---------------------------------------------------------------------------

class TestExperienceStore:

    def test_save_and_load(self, tmp_path):
        store = ExperienceStore(store_dir=str(tmp_path / "exp"))
        exp = _make_experience(code="def f(): return 1", function_name="f")
        store.save(exp)

        loaded = store.load_all()
        assert len(loaded) == 1
        assert loaded[0].function_name == "f"
        assert loaded[0].code == "def f(): return 1"

    def test_deduplication(self, tmp_path):
        store = ExperienceStore(store_dir=str(tmp_path / "exp"))
        exp1 = _make_experience(code="def g(): return 2", function_name="g")
        exp2 = _make_experience(code="def g(): return 2", function_name="g")

        store.save(exp1)
        store.save(exp2)

        loaded = store.load_all()
        assert len(loaded) == 1

    def test_stats(self, tmp_path):
        store = ExperienceStore(store_dir=str(tmp_path / "exp"))

        # Save 3 samples: 2 buggy, 1 clean; 2 GNN-correct, 1 wrong
        store.save(_make_experience(code="def a(): pass", is_buggy=True, gnn_was_correct=True))
        store.save(_make_experience(code="def b(): pass", is_buggy=True, gnn_was_correct=False))
        store.save(_make_experience(code="def c(): pass", is_buggy=False, gnn_was_correct=True))

        stats = store.get_stats()
        assert stats["total"] == 3
        assert stats["buggy"] == 2
        assert stats["clean"] == 1
        assert stats["gnn_accuracy"] == pytest.approx(2 / 3)
        assert stats["since_last_learn"] == 3

    def test_should_learn(self, tmp_path):
        store = ExperienceStore(store_dir=str(tmp_path / "exp"))

        # With min_samples=3, saving 3 samples should trigger learning
        assert not store.should_learn(min_samples=3)
        for i in range(3):
            store.save(_make_experience(code=f"def f{i}(): pass"))
        assert store.should_learn(min_samples=3)

    def test_mark_learned(self, tmp_path):
        store = ExperienceStore(store_dir=str(tmp_path / "exp"))
        store.save(_make_experience(code="def x(): pass"))
        store.save(_make_experience(code="def y(): pass"))

        assert store._index["since_last_learn"] == 2
        store.mark_learned()
        assert store._index["since_last_learn"] == 0
        assert store._index["learn_count"] == 1

    def test_export_dataset(self, tmp_path):
        store = ExperienceStore(store_dir=str(tmp_path / "exp"))

        # One verified (z3_label=0), one counterexample (z3_label=1), one unknown (z3_label=2)
        store.save(_make_experience(code="def ok(): pass", z3_label=0, is_buggy=False,
                                    property_name="none_safety", bug_lines=[5]))
        store.save(_make_experience(code="def bad(): pass", z3_label=1, is_buggy=True,
                                    property_name="division_safety"))
        store.save(_make_experience(code="def unk(): pass", z3_label=2, is_buggy=False))

        dataset = store.export_dataset()

        # Unknown samples are skipped
        assert len(dataset) == 2

        # Check format matches train.py expectations
        for sample in dataset:
            assert "id" in sample
            assert "code" in sample
            assert "is_buggy" in sample
            assert "bug_line" in sample
            assert "bug_type" in sample
            assert "z3_label" in sample

        # Verify the verified sample
        verified_sample = [s for s in dataset if s["code"] == "def ok(): pass"][0]
        assert verified_sample["is_buggy"] is False
        assert verified_sample["z3_label"] == 0
        assert verified_sample["bug_line"] == 5
        assert verified_sample["bug_type"] == "none_safety"

        # Verify the buggy sample
        buggy_sample = [s for s in dataset if s["code"] == "def bad(): pass"][0]
        assert buggy_sample["is_buggy"] is True
        assert buggy_sample["z3_label"] == 1
        assert buggy_sample["bug_line"] is None  # no bug_lines provided


# ---------------------------------------------------------------------------
# TestCollectExperience
# ---------------------------------------------------------------------------

class TestCollectExperience:

    def _make_result(self, code: str, overall: VerificationResult,
                     gnn_buggy: bool = False, gnn_conf: float = 0.5,
                     checks: list | None = None) -> SequentResult:
        """Build a SequentResult with the given verification outcome."""
        result = SequentResult(code=code, function_name="test_fn")
        result.gnn_prediction = GNNPrediction(
            is_buggy=gnn_buggy,
            buggy_confidence=gnn_conf,
            bug_lines=[3] if gnn_buggy else [],
        )
        report = VerificationReport(function_name="test_fn")
        report.overall_result = overall
        report.checks = checks or []
        result.verification = report
        return result

    def test_collects_from_verified_result(self, tmp_path):
        store = ExperienceStore(store_dir=str(tmp_path / "exp"))
        result = self._make_result(
            code="def safe(): return 1",
            overall=VerificationResult.VERIFIED,
            gnn_buggy=False,
            gnn_conf=0.1,
        )

        collect_experience(result, store)

        loaded = store.load_all()
        assert len(loaded) == 1
        assert loaded[0].z3_label == 0
        assert loaded[0].is_buggy is False

    def test_collects_from_buggy_result(self, tmp_path):
        store = ExperienceStore(store_dir=str(tmp_path / "exp"))
        checks = [
            PropertyCheck(
                property_name="division_safety",
                result=VerificationResult.COUNTEREXAMPLE,
                counterexample={"b": 0},
                description="Division by zero possible",
                line=2,
            )
        ]
        result = self._make_result(
            code="def div(a, b): return a / b",
            overall=VerificationResult.COUNTEREXAMPLE,
            gnn_buggy=True,
            gnn_conf=0.95,
            checks=checks,
        )

        collect_experience(result, store)

        loaded = store.load_all()
        assert len(loaded) == 1
        assert loaded[0].z3_label == 1
        assert loaded[0].is_buggy is True
        assert loaded[0].property_name == "division_safety"

    def test_handles_no_verification(self, tmp_path):
        store = ExperienceStore(store_dir=str(tmp_path / "exp"))
        result = SequentResult(code="def f(): pass", function_name="f")
        result.verification = None

        # Should not crash, should not store anything
        collect_experience(result, store)
        assert len(store.load_all()) == 0


# ---------------------------------------------------------------------------
# TestOnlineLearner
# ---------------------------------------------------------------------------

class TestOnlineLearner:

    def test_rollback_no_backup(self, tmp_path):
        model_dir = str(tmp_path / "models")
        checkpoint_path = str(tmp_path / "model.pt")

        learner = OnlineLearner(
            model_dir=model_dir,
            checkpoint_path=checkpoint_path,
            experience_store=ExperienceStore(store_dir=str(tmp_path / "exp")),
        )

        # No backup exists, rollback should return False
        assert learner.rollback() is False

    def test_fine_tune_not_enough_samples(self, tmp_path):
        store = ExperienceStore(store_dir=str(tmp_path / "exp"))
        # Save just 2 samples — way below the default min_samples=20
        store.save(_make_experience(code="def a(): pass", z3_label=0))
        store.save(_make_experience(code="def b(): pass", z3_label=1))

        learner = OnlineLearner(
            model_dir=str(tmp_path / "models"),
            checkpoint_path=str(tmp_path / "model.pt"),
            experience_store=store,
        )

        result = learner.fine_tune(min_samples=20)
        assert "error" in result
        assert "Not enough samples" in result["error"]


# ---------------------------------------------------------------------------
# TestEngineIntegration
# ---------------------------------------------------------------------------

class TestEngineIntegration:

    def test_engine_collects_experience(self, tmp_path, monkeypatch):
        # Patch ExperienceStore default dir to tmp_path so we don't pollute ~/.sequent
        store_dir = str(tmp_path / "exp")
        engine = SequentEngine(model_path=None, self_learn=True)
        engine.experience_store = ExperienceStore(store_dir=store_dir)

        code = "def add(a, b):\n    return a + b"
        result = engine.analyze(code, function_name="add")

        # The engine should have collected experience (Z3 runs and produces a verdict)
        loaded = engine.experience_store.load_all()
        assert len(loaded) >= 1
        assert loaded[0].function_name == "add"
        # Z3 label should be 0 (verified) or at least not crash
        assert loaded[0].z3_label in (0, 1, 2)

    def test_engine_no_learn_flag(self, tmp_path):
        engine = SequentEngine(model_path=None, self_learn=False)
        assert engine.experience_store is None
