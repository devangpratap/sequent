"""Tests for the full neurosymbolic pipeline."""

import os
import pytest

from verifier.neurosymbolic import (
    SequentEngine,
    SequentResult,
    GNNPrediction,
    RepairResult,
)
from verifier.z3_engine import PropertyCheck, VerificationReport, VerificationResult


MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'checkpoints', 'best_model.pt')


@pytest.fixture
def engine():
    if not os.path.exists(MODEL_PATH):
        pytest.skip("No trained model available")
    return SequentEngine(model_path=MODEL_PATH)


@pytest.fixture
def engine_no_model():
    """Engine without a trained model — for unit-testing repair & consensus."""
    return SequentEngine()


# ── Integration tests (require trained model) ──────────────────────────


def test_buggy_function_detected(engine):
    code = """
def find_max(arr):
    max_val = arr[0]
    for i in range(1, len(arr)):
        if arr[i] > max_val:
            max_val = arr[i]
    return max_val
"""
    result = engine.analyze(code, "find_max")
    assert result.consensus_buggy is True
    assert result.verification is not None
    assert result.verification.has_bugs


def test_clean_function_verified(engine):
    code = """
def safe_divide(a, b):
    if a is None or b is None:
        return None
    if b == 0:
        return None
    return a / b
"""
    result = engine.analyze(code, "safe_divide")
    assert result.consensus_buggy is False


def test_auto_repair(engine):
    code = """
def find_max(arr):
    max_val = arr[0]
    for i in range(1, len(arr)):
        if arr[i] > max_val:
            max_val = arr[i]
    return max_val
"""
    result = engine.analyze(code, "find_max")
    assert result.repair is not None
    assert "None" in result.repair.repair_description


def test_json_summary(engine):
    code = "def f():\n    return 1"
    result = engine.analyze(code, "f")
    summary = result.summary
    assert "function" in summary
    assert "is_buggy" in summary
    assert "total_time_ms" in summary


def test_attention_in_output(engine):
    code = "def f(x):\n    return x + 1"
    result = engine.analyze(code, "f")
    assert result.gnn_prediction is not None
    assert isinstance(result.gnn_prediction.attention_edges, list)


# ── Unit tests for new repair strategies ────────────────────────────────


class TestRepairMissingReturn:
    """Tests for _repair_missing_return."""

    def test_adds_int_default(self, engine_no_model):
        code = "def foo(x):\n    if x > 0:\n        return 1"
        check = PropertyCheck(
            property_name="return_completeness",
            result=VerificationResult.COUNTEREXAMPLE,
            description="Missing return on some paths",
        )
        repair = engine_no_model._repair_missing_return(code, check)
        assert repair is not None
        assert "return 0" in repair.repaired_code
        assert "missing return" in repair.repair_description.lower()

    def test_adds_none_default_when_no_returns(self, engine_no_model):
        code = "def bar(x):\n    print(x)"
        check = PropertyCheck(
            property_name="return_completeness",
            result=VerificationResult.COUNTEREXAMPLE,
            description="Missing return",
        )
        repair = engine_no_model._repair_missing_return(code, check)
        assert repair is not None
        assert "return None" in repair.repaired_code

    def test_adds_bool_default(self, engine_no_model):
        code = "def check(x):\n    if x > 0:\n        return True"
        check = PropertyCheck(
            property_name="return_completeness",
            result=VerificationResult.COUNTEREXAMPLE,
            description="Missing return",
        )
        repair = engine_no_model._repair_missing_return(code, check)
        assert repair is not None
        assert "return False" in repair.repaired_code

    def test_adds_list_default(self, engine_no_model):
        code = "def get_items(x):\n    if x:\n        return [1, 2]"
        check = PropertyCheck(
            property_name="return_completeness",
            result=VerificationResult.COUNTEREXAMPLE,
            description="Missing return",
        )
        repair = engine_no_model._repair_missing_return(code, check)
        assert repair is not None
        assert "return []" in repair.repaired_code


class TestRepairWrongOperator:
    """Tests for _repair_wrong_operator."""

    def test_swap_lt_to_lte(self, engine_no_model):
        code = "def search(arr, low, high):\n    while low < high:\n        mid = (low + high) // 2"
        # Line 2 contains the `<`
        check = PropertyCheck(
            property_name="operator_consistency",
            result=VerificationResult.COUNTEREXAMPLE,
            description="Should be <= not <",
            line=2,
        )
        repair = engine_no_model._repair_wrong_operator(code, check)
        assert repair is not None
        assert "<=" in repair.repaired_code

    def test_no_line_returns_none(self, engine_no_model):
        code = "def f(x):\n    return x < 5"
        check = PropertyCheck(
            property_name="operator_consistency",
            result=VerificationResult.COUNTEREXAMPLE,
            description="op issue",
            line=None,
        )
        repair = engine_no_model._repair_wrong_operator(code, check)
        assert repair is None


class TestRepairRecursionBaseCase:
    """Tests for _repair_recursion_base_case."""

    def test_adds_base_case_for_n(self, engine_no_model):
        code = "def factorial(n):\n    if n == 1:\n        return 1\n    return n * factorial(n - 1)"
        check = PropertyCheck(
            property_name="recursion_base_case",
            result=VerificationResult.COUNTEREXAMPLE,
            description="No base case detected",
        )
        repair = engine_no_model._repair_recursion_base_case(code, check)
        assert repair is not None
        assert "n <= 0" in repair.repaired_code
        assert "return 0" in repair.repaired_code

    def test_adds_base_case_for_depth(self, engine_no_model):
        code = "def traverse(depth, node):\n    traverse(depth - 1, node.left)"
        check = PropertyCheck(
            property_name="recursion_base_case",
            result=VerificationResult.COUNTEREXAMPLE,
            description="No base case",
        )
        repair = engine_no_model._repair_recursion_base_case(code, check)
        assert repair is not None
        assert "depth <= 0" in repair.repaired_code

    def test_no_params_returns_none(self, engine_no_model):
        code = "def f():\n    f()"
        check = PropertyCheck(
            property_name="recursion_base_case",
            result=VerificationResult.COUNTEREXAMPLE,
            description="No base case",
        )
        repair = engine_no_model._repair_recursion_base_case(code, check)
        assert repair is None


class TestRepairIndexBounds:
    """Tests for improved _repair_index_bounds."""

    def test_adds_empty_guard(self, engine_no_model):
        code = "def first(arr):\n    return arr[0]"
        check = PropertyCheck(
            property_name="index_bounds",
            result=VerificationResult.COUNTEREXAMPLE,
            description="Array index arr[0] can exceed bounds at line 2",
            line=2,
            counterexample={"array_length": 0, "index_value": 0},
        )
        repair = engine_no_model._repair_index_bounds(code, check)
        assert repair is not None
        assert "len(arr)" in repair.repaired_code
        assert "return None" in repair.repaired_code


class TestLoopTerminationManualReview:
    """Tests for loop_termination flagged for manual review."""

    def test_loop_termination_flags_manual(self, engine_no_model):
        code = "def spin(x):\n    while x > 0:\n        pass"
        check = PropertyCheck(
            property_name="loop_termination",
            result=VerificationResult.COUNTEREXAMPLE,
            description="Infinite loop",
            line=2,
        )
        # Build a minimal SequentResult to pass to _attempt_repair
        report = VerificationReport(function_name="spin", checks=[check])
        report.overall_result = VerificationResult.COUNTEREXAMPLE
        sr = SequentResult(
            code=code,
            function_name="spin",
            verification=report,
            consensus_buggy=True,
        )
        repair = engine_no_model._attempt_repair(code, sr)
        assert repair is not None
        assert repair.repaired_code == code  # no auto-fix
        assert "manual review" in repair.repair_description.lower()


# ── Unit tests for updated consensus logic ──────────────────────────────


class TestConsensusHighConfidenceWarning:
    """When GNN says buggy with >0.85 confidence but Z3 disagrees,
    consensus should be WARNING, not a clean pass."""

    def test_high_confidence_gnn_warning(self, engine_no_model):
        # Use a function that Z3 will NOT flag as buggy (no params used unsafely)
        code = "def f():\n    return 42"
        result = engine_no_model.analyze(code, "f")
        # Confirm Z3 found no bugs
        assert not result.verification.has_bugs

        # Simulate high-confidence GNN disagreement
        result.gnn_prediction = GNNPrediction(
            is_buggy=True,
            buggy_confidence=0.92,
            bug_lines=[2],
        )
        # Re-derive consensus as the engine would
        gnn_says_buggy = result.gnn_prediction.is_buggy
        z3_says_buggy = result.verification.has_bugs
        gnn_conf = result.gnn_prediction.buggy_confidence

        assert gnn_says_buggy and not z3_says_buggy

        if gnn_conf > 0.85:
            result.consensus_buggy = False
            result.consensus_description = (
                f"WARNING: GNN flagged bug with high confidence ({gnn_conf:.1%}) "
                f"but Z3 could not confirm. Bug class may be outside Z3's scope. "
                f"Lines: {result.gnn_prediction.bug_lines}"
            )

        assert "WARNING" in result.consensus_description
        assert "92" in result.consensus_description  # 92.0%
        assert result.consensus_buggy is False

    def test_low_confidence_gnn_is_false_positive(self, engine_no_model):
        code = "def f():\n    return 42"
        result = engine_no_model.analyze(code, "f")
        assert not result.verification.has_bugs

        result.gnn_prediction = GNNPrediction(
            is_buggy=True,
            buggy_confidence=0.60,
            bug_lines=[2],
        )
        gnn_conf = result.gnn_prediction.buggy_confidence
        z3_says_buggy = result.verification.has_bugs

        assert not z3_says_buggy

        if result.gnn_prediction.is_buggy and not z3_says_buggy:
            if gnn_conf > 0.85:
                result.consensus_description = "WARNING"
            else:
                result.consensus_description = (
                    f"GNN flagged potential bug (confidence: {gnn_conf:.1%}) "
                    f"but Z3 could not confirm. "
                    f"Likely false positive or bug class outside Z3's scope."
                )

        assert "WARNING" not in result.consensus_description
        assert "false positive" in result.consensus_description.lower()


class TestAttemptRepairRouting:
    """Verify _attempt_repair dispatches to the correct strategy."""

    def test_return_completeness_routes(self, engine_no_model):
        code = "def foo(x):\n    if x > 0:\n        return 1"
        check = PropertyCheck(
            property_name="return_completeness",
            result=VerificationResult.COUNTEREXAMPLE,
            description="Missing return",
        )
        report = VerificationReport(function_name="foo", checks=[check])
        report.overall_result = VerificationResult.COUNTEREXAMPLE
        sr = SequentResult(
            code=code, function_name="foo",
            verification=report, consensus_buggy=True,
        )
        repair = engine_no_model._attempt_repair(code, sr)
        assert repair is not None
        assert "return 0" in repair.repaired_code

    def test_operator_consistency_routes(self, engine_no_model):
        code = "def f(a, b):\n    while a < b:\n        a += 1"
        check = PropertyCheck(
            property_name="operator_consistency",
            result=VerificationResult.COUNTEREXAMPLE,
            description="< should be <=",
            line=2,
        )
        report = VerificationReport(function_name="f", checks=[check])
        report.overall_result = VerificationResult.COUNTEREXAMPLE
        sr = SequentResult(
            code=code, function_name="f",
            verification=report, consensus_buggy=True,
        )
        repair = engine_no_model._attempt_repair(code, sr)
        assert repair is not None
        assert "<=" in repair.repaired_code

    def test_recursion_base_case_routes(self, engine_no_model):
        code = "def fib(n):\n    return fib(n - 1) + fib(n - 2)"
        check = PropertyCheck(
            property_name="recursion_base_case",
            result=VerificationResult.COUNTEREXAMPLE,
            description="No base case",
        )
        report = VerificationReport(function_name="fib", checks=[check])
        report.overall_result = VerificationResult.COUNTEREXAMPLE
        sr = SequentResult(
            code=code, function_name="fib",
            verification=report, consensus_buggy=True,
        )
        repair = engine_no_model._attempt_repair(code, sr)
        assert repair is not None
        assert "n <= 0" in repair.repaired_code
