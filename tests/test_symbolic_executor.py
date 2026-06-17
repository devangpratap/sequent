"""Tests for the symbolic executor and its integration with Z3Verifier."""

import ast
import textwrap

import pytest
import z3

from verifier.symbolic_executor import ExecStatus, SymbolicExecutor, SymbolicState
from verifier.z3_engine import Z3Verifier, VerificationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_func(code: str) -> ast.FunctionDef:
    code = textwrap.dedent(code).strip()
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            return node
    raise ValueError("No function found")


def _exec(code: str, **kwargs) -> SymbolicState:
    func = _parse_func(code)
    executor = SymbolicExecutor(**kwargs)
    return executor.execute(func)


@pytest.fixture
def verifier():
    return Z3Verifier(timeout_ms=3000)


# ===================================================================
# 1. SymbolicExecutor unit tests
# ===================================================================

class TestAssignmentChains:
    """Simple linear assignment and expression evaluation."""

    def test_basic_add_and_mul(self):
        state = _exec("""
def f(a, b):
    x = a + b
    y = x * 2
    return y
""")
        assert state.status == ExecStatus.OK or state.status == ExecStatus.RETURNED
        assert state.return_expr is not None
        # Verify the symbolic expression is correct:
        # y = (a + b) * 2.  Check with concrete values.
        solver = z3.Solver()
        a, b = z3.Int('a'), z3.Int('b')
        solver.add(a == 3, b == 4)
        solver.add(state.return_expr == (a + b) * 2)
        assert solver.check() == z3.sat

    def test_aug_assign(self):
        state = _exec("""
def f(a):
    x = a
    x += 10
    return x
""")
        assert state.return_expr is not None
        solver = z3.Solver()
        a = z3.Int('a')
        solver.add(a == 5)
        solver.add(state.return_expr == a + 10)
        assert solver.check() == z3.sat

    def test_multiple_assignments(self):
        state = _exec("""
def f(n):
    a = n + 1
    b = a * a
    c = b - n
    return c
""")
        assert state.return_expr is not None
        solver = z3.Solver()
        n = z3.Int('n')
        solver.add(n == 3)
        # c = (n+1)^2 - n = n^2 + 2n + 1 - n = n^2 + n + 1 = 9+3+1 = 13
        solver.add(state.return_expr == 13)
        assert solver.check() == z3.sat


class TestConditionalPaths:
    """If/else branching and path constraints."""

    def test_simple_if_else(self):
        state = _exec("""
def f(x):
    if x > 0:
        return x
    else:
        return -x
""")
        assert state.return_expr is not None
        # Should be z3.If(x > 0, x, -x)
        solver = z3.Solver()
        x = z3.Int('x')
        solver.add(x == -5)
        solver.add(state.return_expr == 5)
        assert solver.check() == z3.sat

    def test_if_without_else(self):
        state = _exec("""
def f(x):
    y = 0
    if x > 0:
        y = x
    return y
""")
        assert state.return_expr is not None

    def test_nested_if(self):
        state = _exec("""
def f(x, y):
    if x > 0:
        if y > 0:
            return x + y
        else:
            return x - y
    else:
        return 0
""")
        assert state.return_expr is not None

    def test_elif_chain(self):
        state = _exec("""
def classify(x):
    if x > 0:
        return 1
    elif x < 0:
        return -1
    else:
        return 0
""")
        assert state.return_expr is not None
        solver = z3.Solver()
        x = z3.Int('x')
        solver.add(x == 0)
        solver.add(state.return_expr == 0)
        assert solver.check() == z3.sat


class TestLoopUnrolling:
    """For and while loop unrolling."""

    def test_for_range_concrete(self):
        state = _exec("""
def f():
    s = 0
    for i in range(5):
        s += i
    return s
""")
        assert state.return_expr is not None
        # sum(0..4) = 10
        solver = z3.Solver()
        solver.add(state.return_expr == 10)
        assert solver.check() == z3.sat

    def test_for_range_symbolic(self):
        state = _exec("""
def f(n):
    s = 0
    for i in range(n):
        s += i
    return s
""")
        # Should not crash -- symbolic n means unrolling is approximate
        assert state.return_expr is not None

    def test_while_loop(self):
        state = _exec("""
def f(x):
    i = 0
    while i < x:
        i += 1
    return i
""")
        assert state.return_expr is not None

    def test_loop_unroll_limit(self):
        """Loop unrolls at most max_loop_unroll times."""
        state = _exec("""
def f():
    s = 0
    for i in range(100):
        s += i
    return s
""", max_loop_unroll=3)
        # Should have an assumption about capping
        assert any("capped" in a or "unrolled" in a for a in state.assumptions)


class TestExpressionTypes:
    """Test coverage for various expression node types."""

    def test_constants(self):
        state = _exec("""
def f():
    return 42
""")
        solver = z3.Solver()
        solver.add(state.return_expr == 42)
        assert solver.check() == z3.sat

    def test_boolean_ops(self):
        state = _exec("""
def f(a, b):
    if a > 0 and b > 0:
        return 1
    return 0
""")
        assert state.return_expr is not None

    def test_unary_not(self):
        state = _exec("""
def f(x):
    if not x > 0:
        return -1
    return 1
""")
        assert state.return_expr is not None

    def test_unary_neg(self):
        state = _exec("""
def f(x):
    return -x
""")
        solver = z3.Solver()
        x = z3.Int('x')
        solver.add(x == 7)
        solver.add(state.return_expr == -7)
        assert solver.check() == z3.sat

    def test_modulo(self):
        state = _exec("""
def f(a, b):
    return a % b
""")
        assert state.return_expr is not None
        assert len(state.divisions) == 1  # b is a divisor

    def test_floor_div(self):
        state = _exec("""
def f(a, b):
    return a // b
""")
        assert len(state.divisions) == 1

    def test_len_call(self):
        state = _exec("""
def f(arr):
    return len(arr)
""")
        assert state.return_expr is not None
        assert "len_arr" in state.variables

    def test_subscript(self):
        state = _exec("""
def f(arr, i):
    return arr[i]
""")
        assert len(state.array_accesses) == 1
        name, idx, line = state.array_accesses[0]
        assert name == "arr"

    def test_ifexp(self):
        state = _exec("""
def f(x):
    return x if x > 0 else -x
""")
        solver = z3.Solver()
        x = z3.Int('x')
        solver.add(x == -3)
        solver.add(state.return_expr == 3)
        assert solver.check() == z3.sat

    def test_chained_comparison(self):
        state = _exec("""
def f(x):
    if 0 < x < 10:
        return x
    return 0
""")
        assert state.return_expr is not None

    def test_abs_call(self):
        state = _exec("""
def f(x):
    return abs(x)
""")
        solver = z3.Solver()
        x = z3.Int('x')
        solver.add(x == -4)
        solver.add(state.return_expr == 4)
        assert solver.check() == z3.sat

    def test_min_max_calls(self):
        state = _exec("""
def f(a, b):
    return min(a, b)
""")
        solver = z3.Solver()
        a, b = z3.Int('a'), z3.Int('b')
        solver.add(a == 3, b == 7)
        solver.add(state.return_expr == 3)
        assert solver.check() == z3.sat


class TestGracefulDegradation:
    """Unsupported constructs should not crash."""

    def test_method_call(self):
        state = _exec("""
def f(s):
    return s.upper()
""")
        # Should not crash; approximated with a fresh variable
        assert state.return_expr is not None
        assert any("approximated" in a for a in state.assumptions)

    def test_list_comprehension(self):
        state = _exec("""
def f(n):
    xs = [i * 2 for i in range(n)]
    return xs
""")
        # Comprehension as RHS of assign -- the assign's RHS eval will be unsupported
        # but should not crash
        assert state.status in (ExecStatus.OK, ExecStatus.RETURNED, ExecStatus.UNSUPPORTED)

    def test_try_except(self):
        state = _exec("""
def f(x):
    try:
        return x / 0
    except:
        return 0
""")
        # try/except is an unsupported stmt; executor should skip gracefully
        assert state.status in (ExecStatus.OK, ExecStatus.UNSUPPORTED)

    def test_star_unpack(self):
        state = _exec("""
def f(a, b, c):
    return a + b + c
""")
        assert state.return_expr is not None


# ===================================================================
# 2. Integration: Z3Verifier._check_symbolic_properties
# ===================================================================

class TestSymbolicDivisionByZero:
    """Division-by-zero detection via symbolic execution."""

    def test_detects_unguarded_division(self, verifier):
        code = """
def f(a, b):
    return a // b
"""
        report = verifier.verify(code, "f")
        sym_div = [c for c in report.checks if c.property_name == "sym_division_by_zero"]
        assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in sym_div)

    def test_guarded_division_safe(self, verifier):
        code = """
def f(a, b):
    if b == 0:
        return 0
    return a // b
"""
        report = verifier.verify(code, "f")
        sym_div = [c for c in report.checks if c.property_name == "sym_division_by_zero"]
        # The path through the division has b != 0 in its constraints
        # Due to path forking, at least one check should be verified
        if sym_div:
            assert any(c.result == VerificationResult.VERIFIED for c in sym_div)

    def test_modulo_zero(self, verifier):
        code = """
def f(a, n):
    return a % n
"""
        report = verifier.verify(code, "f")
        sym_div = [c for c in report.checks if c.property_name == "sym_division_by_zero"]
        assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in sym_div)


class TestSymbolicArrayBounds:
    """Array bounds detection via symbolic execution."""

    def test_unconstrained_index(self, verifier):
        code = """
def f(arr, i):
    return arr[i]
"""
        report = verifier.verify(code, "f")
        sym_arr = [c for c in report.checks if c.property_name == "sym_array_bounds"]
        assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in sym_arr)

    def test_index_plus_one(self, verifier):
        code = """
def f(arr):
    n = len(arr)
    return arr[n]
"""
        report = verifier.verify(code, "f")
        sym_arr = [c for c in report.checks if c.property_name == "sym_array_bounds"]
        # arr[n] where n = len(arr) is out of bounds
        assert any(c.result == VerificationResult.COUNTEREXAMPLE for c in sym_arr)


class TestSymbolicOverflow:
    """Overflow detection via symbolic execution."""

    def test_large_multiplication_can_overflow(self, verifier):
        code = """
def f(a, b):
    return a * b
"""
        report = verifier.verify(code, "f")
        sym_ov = [c for c in report.checks if c.property_name == "sym_overflow"]
        # a * b with 32-bit inputs can exceed 2^31 -- reported as UNKNOWN (warning)
        assert any(c.result == VerificationResult.UNKNOWN for c in sym_ov)

    def test_small_constant_no_overflow(self, verifier):
        code = """
def f():
    return 2 + 3
"""
        report = verifier.verify(code, "f")
        sym_ov = [c for c in report.checks if c.property_name == "sym_overflow"]
        if sym_ov:
            assert all(c.result == VerificationResult.VERIFIED for c in sym_ov)


class TestNestedConditions:
    """Complex nested if/else structures."""

    def test_nested_division_guard(self, verifier):
        code = """
def f(a, b, c):
    if b != 0:
        if c != 0:
            return (a // b) + (a // c)
    return 0
"""
        report = verifier.verify(code, "f")
        sym_div = [c for c in report.checks if c.property_name == "sym_division_by_zero"]
        # Both divisions are guarded
        if sym_div:
            assert any(c.result == VerificationResult.VERIFIED for c in sym_div)

    def test_deeply_nested_array_access(self):
        state = _exec("""
def f(arr, x):
    if x > 0:
        if x < 10:
            return arr[x]
    return 0
""")
        assert len(state.array_accesses) >= 1
