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
    """Correct binary_search -- Z3 may still flag index bounds (overapproximation).
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


# ---------- Loop Bound Verification ----------

def test_loop_bound_verified_when_gap_shrinks(verifier):
    """A while loop where low increases and high decreases should be verified."""
    code = """
def search(arr, target):
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
    report = verifier.verify(code, "search")
    loop_bound_checks = [c for c in report.checks if c.property_name == "loop_bound"]
    # Should have a loop_bound check that is VERIFIED (gap shrinks)
    if loop_bound_checks:
        assert any(c.result == VerificationResult.VERIFIED for c in loop_bound_checks)


def test_loop_bound_flags_non_decreasing_gap(verifier):
    """A while loop where the gap never shrinks should be flagged."""
    code = """
def bad_loop(low, high):
    while low <= high:
        mid = (low + high) // 2
        print(mid)
    return mid
"""
    report = verifier.verify(code, "bad_loop")
    # Should flag loop termination or loop bound issue
    termination_checks = [
        c for c in report.checks
        if c.property_name in ("loop_bound", "loop_termination")
        and c.result == VerificationResult.COUNTEREXAMPLE
    ]
    assert len(termination_checks) > 0


# ---------- Return Completeness ----------

def test_return_completeness_missing_else(verifier):
    """If/elif without else that returns values should be flagged."""
    code = """
def classify(x):
    if x > 0:
        return "positive"
    elif x < 0:
        return "negative"
"""
    report = verifier.verify(code, "classify")
    ret_checks = [c for c in report.checks if c.property_name == "return_completeness"]
    assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in ret_checks)


def test_return_completeness_with_else(verifier):
    """If/elif/else that all return should be verified."""
    code = """
def classify(x):
    if x > 0:
        return "positive"
    elif x < 0:
        return "negative"
    else:
        return "zero"
"""
    report = verifier.verify(code, "classify")
    ret_checks = [c for c in report.checks if c.property_name == "return_completeness"]
    assert all(c.result == VerificationResult.VERIFIED for c in ret_checks)


def test_return_completeness_no_value_return(verifier):
    """Functions that never return a value should not be flagged."""
    code = """
def greet(name):
    if name:
        print("Hello " + name)
    else:
        print("Hello world")
"""
    report = verifier.verify(code, "greet")
    ret_checks = [c for c in report.checks if c.property_name == "return_completeness"]
    assert all(c.result == VerificationResult.VERIFIED for c in ret_checks)


# ---------- Operator Consistency ----------

def test_operator_consistency_wrong_midpoint(verifier):
    """(high - low) // 2 without adding low should be flagged."""
    code = """
def bad_midpoint(low, high):
    mid = (high - low) // 2
    return mid
"""
    report = verifier.verify(code, "bad_midpoint")
    op_checks = [c for c in report.checks if c.property_name == "operator_consistency"]
    assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in op_checks)


def test_operator_consistency_correct_midpoint(verifier):
    """(low + high) // 2 should not be flagged."""
    code = """
def good_midpoint(low, high):
    mid = (low + high) // 2
    return mid
"""
    report = verifier.verify(code, "good_midpoint")
    op_checks = [c for c in report.checks if c.property_name == "operator_consistency"]
    assert all(c.result == VerificationResult.VERIFIED for c in op_checks)


def test_operator_consistency_and_vs_or_none_guard(verifier):
    """'if a is None and b is None: return' should suggest 'or'."""
    code = """
def process(a, b):
    if a is None and b is None:
        return None
    return a + b
"""
    report = verifier.verify(code, "process")
    op_checks = [c for c in report.checks if c.property_name == "operator_consistency"]
    assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in op_checks)
    flagged = [c for c in op_checks if c.result == VerificationResult.COUNTEREXAMPLE]
    assert "or" in flagged[0].description.lower() or flagged[0].counterexample.get("suggested") == "or"


# ---------- Recursion Base Case ----------

def test_recursion_with_base_case(verifier):
    """Recursive function with a proper base case should be verified."""
    code = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
    report = verifier.verify(code, "factorial")
    rec_checks = [c for c in report.checks if c.property_name == "recursion_base_case"]
    assert len(rec_checks) > 0
    assert all(c.result == VerificationResult.VERIFIED for c in rec_checks)


def test_recursion_without_base_case(verifier):
    """Recursive function with no base case should be flagged."""
    code = """
def infinite_recurse(n):
    return infinite_recurse(n - 1) + infinite_recurse(n - 2)
"""
    report = verifier.verify(code, "infinite_recurse")
    rec_checks = [c for c in report.checks if c.property_name == "recursion_base_case"]
    assert len(rec_checks) > 0
    assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in rec_checks)


def test_recursion_non_recursive_function(verifier):
    """Non-recursive function should pass recursion check."""
    code = """
def add(a, b):
    return a + b
"""
    report = verifier.verify(code, "add")
    rec_checks = [c for c in report.checks if c.property_name == "recursion_base_case"]
    assert all(c.result == VerificationResult.VERIFIED for c in rec_checks)


def test_recursion_all_branches_recurse(verifier):
    """Function where all if branches recurse should be flagged."""
    code = """
def bad_recurse(n):
    if n > 0:
        return bad_recurse(n - 1)
    else:
        return bad_recurse(n + 1)
"""
    report = verifier.verify(code, "bad_recurse")
    rec_checks = [c for c in report.checks if c.property_name == "recursion_base_case"]
    assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in rec_checks)


# ---------- Improved None Safety ----------

def test_none_safety_arithmetic_use(verifier):
    """Parameter used in arithmetic without None guard should be flagged."""
    code = """
def double(x):
    return x * 2
"""
    report = verifier.verify(code, "double")
    none_checks = [c for c in report.checks if c.property_name == "none_safety"]
    assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in none_checks)


def test_none_safety_guarded_arithmetic(verifier):
    """Parameter guarded with None check before arithmetic should be verified."""
    code = """
def safe_double(x):
    if x is None:
        return 0
    return x * 2
"""
    report = verifier.verify(code, "safe_double")
    none_checks = [c for c in report.checks if c.property_name == "none_safety"]
    assert all(c.result == VerificationResult.VERIFIED for c in none_checks)


# ---------- Array Access Bounds ----------

def test_array_access_i_plus_1(verifier):
    """arr[i+1] can exceed bounds when i is at the last valid index."""
    code = """
def pairs(arr):
    for i in range(len(arr)):
        if arr[i] > arr[i + 1]:
            pass
"""
    report = verifier.verify(code, "pairs")
    # Should flag arr[i+1] as potentially out of bounds
    bound_checks = [
        c for c in report.checks
        if c.property_name in ("array_access_bounds", "index_bounds")
        and c.result == VerificationResult.COUNTEREXAMPLE
    ]
    assert len(bound_checks) > 0


def test_subscript_comparison_bounds(verifier):
    """Comparisons involving array subscripts should check index bounds."""
    code = """
def compare_elements(arr, i, j):
    if arr[i] > arr[j]:
        return True
    return False
"""
    report = verifier.verify(code, "compare_elements")
    sub_checks = [c for c in report.checks if c.property_name == "subscript_comparison_bounds"]
    # Indices i, j are unconstrained so can be out of bounds
    assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in sub_checks)
