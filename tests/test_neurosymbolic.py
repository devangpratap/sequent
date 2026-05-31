"""Tests for the full neurosymbolic pipeline."""

import os
import pytest

from verifier.neurosymbolic import SequentEngine


MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'checkpoints', 'best_model.pt')


@pytest.fixture
def engine():
    if not os.path.exists(MODEL_PATH):
        pytest.skip("No trained model available")
    return SequentEngine(model_path=MODEL_PATH)


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
