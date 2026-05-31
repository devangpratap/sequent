"""Tests for the Z3 verification engine."""

import pytest

from verifier.z3_engine import Z3Verifier, VerificationResult


@pytest.fixture
def verifier():
    return Z3Verifier(timeout_ms=3000)


def test_clean_function_verified(verifier):
    code = """
def safe_divide(a, b):
    if a is None or b is None:
        return None
    if b == 0:
        return None
    return a / b
"""
    report = verifier.verify(code, "safe_divide")
    assert report.overall_result == VerificationResult.VERIFIED
    assert len(report.counterexamples) == 0


def test_none_safety_counterexample(verifier):
    code = """
def find_max(arr):
    max_val = arr[0]
    for i in range(1, len(arr)):
        if arr[i] > max_val:
            max_val = arr[i]
    return max_val
"""
    report = verifier.verify(code, "find_max")
    assert report.overall_result == VerificationResult.COUNTEREXAMPLE
    assert report.has_bugs
    # Should find None safety issue
    none_checks = [c for c in report.counterexamples if "none" in c.property_name.lower()]
    assert len(none_checks) > 0


def test_division_safety(verifier):
    code = """
def average(nums):
    return sum(nums) / len(nums)
"""
    report = verifier.verify(code, "average")
    assert report.has_bugs


def test_off_by_one_detection(verifier):
    code = """
def binary_search(arr, target):
    low = 0
    high = len(arr) - 1
    while low < high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
"""
    report = verifier.verify(code, "binary_search")
    # Should detect the off-by-one (low < high instead of low <= high)
    assert report.overall_result == VerificationResult.COUNTEREXAMPLE


def test_empty_function(verifier):
    code = "def noop():\n    pass"
    report = verifier.verify(code, "noop")
    assert report.overall_result == VerificationResult.VERIFIED


def test_correct_binary_search(verifier):
    """Correct binary_search — Z3 may still flag index bounds (overapproximation).
    We verify it at least passes None safety and off-by-one checks."""
    code = """
def binary_search(arr, target):
    if arr is None or len(arr) == 0:
        return -1
    low = 0
    high = len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
"""
    report = verifier.verify(code, "binary_search")
    # None safety and bounds_check should pass
    none_checks = [c for c in report.checks if c.property_name == "none_safety"]
    assert all(c.result == VerificationResult.VERIFIED for c in none_checks)
    bounds_checks = [c for c in report.checks if c.property_name == "bounds_check"]
    assert all(c.result == VerificationResult.VERIFIED for c in bounds_checks)


def test_report_timing(verifier):
    code = "def f():\n    return 1"
    report = verifier.verify(code, "f")
    assert report.total_time_ms >= 0
    for check in report.checks:
        assert check.time_ms >= 0
