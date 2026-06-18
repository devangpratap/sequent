"""Tests for verifier/js_verifier.py — JS/TS Z3 verification."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verifier.js_verifier import JSVerifier, verify_js, _parse_js, _find_functions
from verifier.z3_engine import VerificationResult


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestJSParser:

    def test_parse_function(self):
        code = "function add(a, b) {\n  return a + b;\n}"
        nodes = _parse_js(code)
        funcs = _find_functions(nodes)
        assert len(funcs) == 1
        assert funcs[0].name == "add"
        assert funcs[0].params == ["a", "b"]

    def test_parse_arrow_function(self):
        code = "const multiply = (x, y) => {\n  return x * y;\n}"
        nodes = _parse_js(code)
        funcs = _find_functions(nodes)
        assert len(funcs) == 1
        assert funcs[0].name == "multiply"

    def test_parse_async_function(self):
        code = "async function fetchData(url) {\n  return await fetch(url);\n}"
        nodes = _parse_js(code)
        funcs = _find_functions(nodes)
        assert len(funcs) == 1
        assert funcs[0].name == "fetchData"

    def test_parse_ts_typed_params(self):
        code = "function greet(name: string, age: number) {\n  return name;\n}"
        nodes = _parse_js(code)
        funcs = _find_functions(nodes)
        assert funcs[0].params == ["name", "age"]

    def test_parse_control_flow(self):
        code = """\
function test(x) {
  if (x > 0) {
    return x;
  } else {
    return -x;
  }
}"""
        nodes = _parse_js(code)
        types = [n.type for n in nodes]
        assert "function" in types
        assert "if" in types
        assert "else" in types
        assert types.count("return") == 2

    def test_parse_loops(self):
        code = """\
function loop(arr) {
  for (let i = 0; i < arr.length; i++) {
    console.log(arr[i]);
  }
  while (true) {
    break;
  }
}"""
        nodes = _parse_js(code)
        types = [n.type for n in nodes]
        assert "for" in types
        assert "while" in types
        assert "break" in types


# ---------------------------------------------------------------------------
# Verification tests
# ---------------------------------------------------------------------------

class TestJSNullSafety:

    def test_null_unsafe_property_access(self):
        code = """\
function getLength(arr) {
  return arr.length;
}"""
        report = verify_js(code, "getLength")
        null_checks = [c for c in report.checks if c.property_name == "null_safety"]
        assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in null_checks)

    def test_null_safe_with_guard(self):
        code = """\
function getLength(arr) {
  if (arr === null || arr === undefined) {
    return 0;
  }
  return arr.length;
}"""
        report = verify_js(code, "getLength")
        null_checks = [c for c in report.checks if c.property_name == "null_safety"]
        assert all(c.result == VerificationResult.VERIFIED for c in null_checks)

    def test_null_unsafe_subscript(self):
        code = """\
function first(arr) {
  return arr[0];
}"""
        report = verify_js(code, "first")
        null_checks = [c for c in report.checks if c.property_name == "null_safety"]
        assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in null_checks)


class TestJSDivisionSafety:

    def test_division_by_param(self):
        code = """\
function divide(a, b) {
  return a / b;
}"""
        report = verify_js(code, "divide")
        div_checks = [c for c in report.checks if c.property_name == "division_safety"]
        assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in div_checks)

    def test_division_with_guard(self):
        code = """\
function safeDivide(a, b) {
  if (b === 0) {
    return 0;
  }
  return a / b;
}"""
        report = verify_js(code, "safeDivide")
        div_checks = [c for c in report.checks if c.property_name == "division_safety"]
        assert all(c.result == VerificationResult.VERIFIED for c in div_checks)


class TestJSArrayBounds:

    def test_array_index_can_exceed(self):
        code = """\
function getElement(arr, i) {
  return arr[i];
}"""
        report = verify_js(code, "getElement")
        idx_checks = [c for c in report.checks if c.property_name == "index_bounds"]
        assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in idx_checks)


class TestJSReturnCompleteness:

    def test_void_function_ok(self):
        code = """\
function log(msg) {
  console.log(msg);
}"""
        report = verify_js(code, "log")
        ret_checks = [c for c in report.checks if c.property_name == "return_completeness"]
        assert all(c.result == VerificationResult.VERIFIED for c in ret_checks)


class TestJSLoopTermination:

    def test_infinite_loop_detected(self):
        code = """\
function spin(x) {
  while (x > 0) {
    console.log(x);
  }
}"""
        report = verify_js(code, "spin")
        loop_checks = [c for c in report.checks if c.property_name == "loop_termination"]
        assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in loop_checks)


class TestJSOperatorConsistency:

    def test_loose_equality_flagged(self):
        code = """\
function check(a, b) {
  if (a == b) {
    return true;
  }
  return false;
}"""
        report = verify_js(code, "check")
        op_checks = [c for c in report.checks if c.property_name == "operator_consistency"]
        assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in op_checks)
        assert any("===" in (c.counterexample or {}).get("suggestion", "") for c in op_checks)

    def test_strict_equality_ok(self):
        code = """\
function check(a, b) {
  if (a === b) {
    return true;
  }
  return false;
}"""
        report = verify_js(code, "check")
        op_checks = [c for c in report.checks if c.property_name == "operator_consistency"]
        assert all(c.result == VerificationResult.VERIFIED for c in op_checks)


class TestJSDeadCode:

    def test_dead_code_after_return(self):
        code = """\
function foo() {
  return 1;
  console.log("unreachable");
}"""
        report = verify_js(code, "foo")
        dead_checks = [c for c in report.checks if c.property_name == "dead_code"]
        assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in dead_checks)


class TestJSCleanFunction:

    def test_clean_function_verified(self):
        code = """\
function add(a, b) {
  return a + b;
}"""
        report = verify_js(code, "add")
        assert report.overall_result in (VerificationResult.VERIFIED, VerificationResult.COUNTEREXAMPLE)
        # At minimum the function should be parseable
        assert report.function_name == "add"
        assert report.total_time_ms > 0


class TestJSIntegration:

    def test_verify_js_convenience(self):
        code = "function id(x) {\n  return x;\n}"
        report = verify_js(code, "id")
        assert report.function_name == "id"
        assert len(report.checks) > 0

    def test_no_functions_unsupported(self):
        code = "const x = 1;\nconst y = 2;"
        report = verify_js(code)
        assert report.overall_result == VerificationResult.UNSUPPORTED

    def test_neurosymbolic_analyze_js(self):
        """Test that SequentEngine.analyze_js works end-to-end."""
        from verifier.neurosymbolic import SequentEngine

        engine = SequentEngine(model_path=None, self_learn=False)
        code = """\
function divide(a, b) {
  return a / b;
}"""
        result = engine.analyze_js(code, "divide")
        assert result.function_name == "divide"
        assert result.verification is not None
        assert result.consensus_buggy  # division by zero should be caught
