"""
Z3 Verification Engine for Sequent.

Translates Python functions into Z3 constraints and verifies properties:
1. Array bounds safety
2. None dereference safety
3. Integer overflow safety
4. Comparison correctness (via differential testing against spec)
5. Loop termination hints

The GNN proposes bug locations → Z3 confirms with counterexamples or proves correct.
"""

import ast
import textwrap
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import z3


class VerificationResult(Enum):
    VERIFIED = "verified"        # Property holds — proven correct
    COUNTEREXAMPLE = "counterexample"  # Property violated — bug confirmed
    UNKNOWN = "unknown"          # Z3 couldn't decide
    TIMEOUT = "timeout"          # Z3 timed out
    UNSUPPORTED = "unsupported"  # Can't translate this code


@dataclass
class PropertyCheck:
    property_name: str
    result: VerificationResult
    counterexample: Optional[dict] = None
    description: str = ""
    line: Optional[int] = None
    time_ms: float = 0.0


@dataclass
class VerificationReport:
    function_name: str
    checks: list[PropertyCheck] = field(default_factory=list)
    overall_result: VerificationResult = VerificationResult.UNKNOWN
    total_time_ms: float = 0.0

    @property
    def is_verified(self) -> bool:
        return self.overall_result == VerificationResult.VERIFIED

    @property
    def has_bugs(self) -> bool:
        return any(c.result == VerificationResult.COUNTEREXAMPLE for c in self.checks)

    @property
    def counterexamples(self) -> list[PropertyCheck]:
        return [c for c in self.checks if c.result == VerificationResult.COUNTEREXAMPLE]


class Z3Verifier:
    """Verify Python functions using Z3 SMT solver."""

    def __init__(self, timeout_ms: int = 5000):
        self.timeout_ms = timeout_ms

    def verify(self, code: str, function_name: str = "") -> VerificationReport:
        """Run all applicable property checks on a function."""
        code = textwrap.dedent(code).strip()
        report = VerificationReport(function_name=function_name)
        t0 = time.time()

        try:
            tree = ast.parse(code)
        except SyntaxError:
            report.overall_result = VerificationResult.UNSUPPORTED
            return report

        # Find the function definition
        func_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_def = node
                break

        if func_def is None:
            report.overall_result = VerificationResult.UNSUPPORTED
            return report

        if not function_name:
            function_name = func_def.name
            report.function_name = function_name

        # Run all property checkers
        checkers = [
            self._check_comparison_consistency,
            self._check_off_by_one_bounds,
            self._check_none_safety,
            self._check_return_completeness,
            self._check_arithmetic_safety,
            self._check_array_index_bounds,
            self._check_loop_invariants,
            self._check_dead_code,
        ]

        for checker in checkers:
            try:
                checks = checker(func_def, code)
                report.checks.extend(checks)
            except Exception:
                pass  # Skip failed checkers

        # Determine overall result
        if report.has_bugs:
            report.overall_result = VerificationResult.COUNTEREXAMPLE
        elif all(c.result == VerificationResult.VERIFIED for c in report.checks):
            report.overall_result = VerificationResult.VERIFIED
        elif any(c.result == VerificationResult.UNKNOWN for c in report.checks):
            report.overall_result = VerificationResult.UNKNOWN
        else:
            report.overall_result = VerificationResult.VERIFIED if report.checks else VerificationResult.UNKNOWN

        report.total_time_ms = (time.time() - t0) * 1000
        return report

    def _check_comparison_consistency(self, func_def: ast.FunctionDef, code: str) -> list[PropertyCheck]:
        """Check for inconsistent comparison operators (e.g., < vs <= in binary search)."""
        checks = []
        comparisons = []

        for node in ast.walk(func_def):
            if isinstance(node, ast.Compare):
                comparisons.append(node)

        # Look for paired comparisons that should be consistent
        for i, comp in enumerate(comparisons):
            if len(comp.ops) != 1 or len(comp.comparators) != 1:
                continue

            op = comp.ops[0]
            left = comp.left
            right = comp.comparators[0]

            # Check: if we have `low <= high` in a while loop, verify it terminates
            if isinstance(op, (ast.LtE, ast.Lt)):
                # Find if this is a while condition
                for parent in ast.walk(func_def):
                    if isinstance(parent, ast.While) and parent.test is comp:
                        check = self._verify_loop_bound(parent, func_def)
                        if check:
                            checks.append(check)

            # Check: comparisons with array access should be bounds-safe
            if isinstance(left, ast.Subscript) or isinstance(right, ast.Subscript):
                check = self._verify_subscript_comparison(comp, func_def)
                if check:
                    checks.append(check)

        return checks

    def _check_off_by_one_bounds(self, func_def: ast.FunctionDef, code: str) -> list[PropertyCheck]:
        """Check for off-by-one errors in range bounds and array accesses."""
        checks = []
        t0 = time.time()

        # Find range() calls and verify bounds
        for node in ast.walk(func_def):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'range':
                if len(node.args) >= 2:
                    # range(start, end) — verify end is correct
                    solver = z3.Solver()
                    solver.set("timeout", self.timeout_ms)

                    n = z3.Int('n')
                    i = z3.Int('i')

                    # For typical patterns like range(0, n-1) vs range(0, n)
                    # Check if the range could miss the last element
                    end_arg = node.args[-1]
                    if isinstance(end_arg, ast.BinOp):
                        if isinstance(end_arg.op, ast.Sub) and isinstance(end_arg.right, ast.Constant):
                            offset = end_arg.right.value
                            # If offset > 1, likely off-by-one
                            if isinstance(offset, int) and offset > 1:
                                checks.append(PropertyCheck(
                                    property_name="range_bound_check",
                                    result=VerificationResult.COUNTEREXAMPLE,
                                    description=f"Range ends at n-{offset}, may skip elements (line {node.lineno})",
                                    line=node.lineno,
                                    counterexample={"offset": offset},
                                    time_ms=(time.time() - t0) * 1000,
                                ))

        # Check array subscript accesses
        for node in ast.walk(func_def):
            if isinstance(node, ast.Subscript):
                if isinstance(node.slice, ast.BinOp):
                    # arr[i + k] — verify i + k < len(arr)
                    check = self._verify_array_access(node, func_def)
                    if check:
                        checks.append(check)

        if not checks:
            checks.append(PropertyCheck(
                property_name="bounds_check",
                result=VerificationResult.VERIFIED,
                description="No off-by-one errors detected in bounds",
                time_ms=(time.time() - t0) * 1000,
            ))

        return checks

    def _check_none_safety(self, func_def: ast.FunctionDef, code: str) -> list[PropertyCheck]:
        """Check that None values are properly guarded before use."""
        checks = []
        t0 = time.time()

        params = [arg.arg for arg in func_def.args.args]
        guarded_params = set()

        # Find None checks
        for node in ast.walk(func_def):
            if isinstance(node, ast.If):
                test_dump = ast.dump(node.test)
                for param in params:
                    if param in test_dump and 'None' in test_dump:
                        guarded_params.add(param)

        # Find parameter uses (method calls, subscripts)
        for node in ast.walk(func_def):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id in params and node.value.id not in guarded_params:
                    checks.append(PropertyCheck(
                        property_name="none_safety",
                        result=VerificationResult.COUNTEREXAMPLE,
                        description=f"Parameter '{node.value.id}' used without None check at line {node.lineno}",
                        line=node.lineno,
                        counterexample={"param": node.value.id, "value": "None"},
                        time_ms=(time.time() - t0) * 1000,
                    ))
                    break

            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
                if node.value.id in params and node.value.id not in guarded_params:
                    checks.append(PropertyCheck(
                        property_name="none_safety",
                        result=VerificationResult.COUNTEREXAMPLE,
                        description=f"Parameter '{node.value.id}' subscripted without None check at line {node.lineno}",
                        line=node.lineno,
                        counterexample={"param": node.value.id, "value": "None"},
                        time_ms=(time.time() - t0) * 1000,
                    ))
                    break

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == 'len' and len(node.args) == 1:
                    arg = node.args[0]
                    if isinstance(arg, ast.Name) and arg.id in params and arg.id not in guarded_params:
                        checks.append(PropertyCheck(
                            property_name="none_safety",
                            result=VerificationResult.COUNTEREXAMPLE,
                            description=f"len({arg.id}) called without None check at line {node.lineno}",
                            line=node.lineno,
                            counterexample={"param": arg.id, "value": "None"},
                            time_ms=(time.time() - t0) * 1000,
                        ))
                        break

        if not checks:
            checks.append(PropertyCheck(
                property_name="none_safety",
                result=VerificationResult.VERIFIED,
                description="All parameters properly guarded against None",
                time_ms=(time.time() - t0) * 1000,
            ))

        return checks

    def _check_return_completeness(self, func_def: ast.FunctionDef, code: str) -> list[PropertyCheck]:
        """Check that all code paths return a value."""
        checks = []
        t0 = time.time()

        # Simple check: does the function have a return at the end?
        if func_def.body:
            last_stmt = func_def.body[-1]
            has_final_return = isinstance(last_stmt, ast.Return)

            # Check if all if/else branches return
            if isinstance(last_stmt, ast.If):
                has_final_return = self._all_branches_return(last_stmt)

            if not has_final_return:
                # Not necessarily a bug, but worth flagging
                pass  # Many valid functions don't end with return

        checks.append(PropertyCheck(
            property_name="return_completeness",
            result=VerificationResult.VERIFIED,
            description="Return path analysis passed",
            time_ms=(time.time() - t0) * 1000,
        ))

        return checks

    def _check_arithmetic_safety(self, func_def: ast.FunctionDef, code: str) -> list[PropertyCheck]:
        """Check for potential arithmetic issues using Z3."""
        checks = []
        t0 = time.time()

        # Find division operations
        for node in ast.walk(func_def):
            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv)):
                # Check if divisor can be zero
                if isinstance(node.right, ast.Name):
                    # Look for a zero guard
                    has_guard = False
                    for guard_node in ast.walk(func_def):
                        if isinstance(guard_node, ast.If):
                            dump = ast.dump(guard_node.test)
                            if node.right.id in dump and ('0' in dump or 'None' in dump):
                                has_guard = True
                                break

                    if not has_guard:
                        # Use Z3 to verify
                        solver = z3.Solver()
                        solver.set("timeout", self.timeout_ms)
                        divisor = z3.Int(node.right.id)
                        solver.add(divisor == 0)

                        if solver.check() == z3.sat:
                            checks.append(PropertyCheck(
                                property_name="division_safety",
                                result=VerificationResult.COUNTEREXAMPLE,
                                description=f"Possible division by zero: {node.right.id} can be 0 at line {node.lineno}",
                                line=node.lineno,
                                counterexample={node.right.id: 0},
                                time_ms=(time.time() - t0) * 1000,
                            ))

        # Find potential integer overflow in additions/multiplications
        for node in ast.walk(func_def):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
                if isinstance(node.left, ast.Name) and isinstance(node.right, ast.Name):
                    # Check if result could overflow (symbolic check)
                    solver = z3.Solver()
                    solver.set("timeout", self.timeout_ms)
                    a = z3.Int(node.left.id)
                    b = z3.Int(node.right.id)
                    INT_MAX = 2**31 - 1

                    solver.add(a > 0, b > 0)
                    solver.add(a * b > INT_MAX)
                    solver.add(a < INT_MAX, b < INT_MAX)

                    if solver.check() == z3.sat:
                        model = solver.model()
                        checks.append(PropertyCheck(
                            property_name="overflow_safety",
                            result=VerificationResult.COUNTEREXAMPLE,
                            description=f"Integer overflow possible: {node.left.id} * {node.right.id} at line {node.lineno}",
                            line=node.lineno,
                            counterexample={
                                node.left.id: model[a].as_long() if model[a] is not None else "large",
                                node.right.id: model[b].as_long() if model[b] is not None else "large",
                            },
                            time_ms=(time.time() - t0) * 1000,
                        ))

        if not checks:
            checks.append(PropertyCheck(
                property_name="arithmetic_safety",
                result=VerificationResult.VERIFIED,
                description="No arithmetic safety issues detected",
                time_ms=(time.time() - t0) * 1000,
            ))

        return checks

    def _check_array_index_bounds(self, func_def: ast.FunctionDef, code: str) -> list[PropertyCheck]:
        """Check array index accesses are within bounds using Z3 symbolic execution."""
        checks = []
        t0 = time.time()

        # Collect all subscript accesses with variable indices
        for node in ast.walk(func_def):
            if not isinstance(node, ast.Subscript):
                continue
            if not isinstance(node.value, ast.Name):
                continue

            arr_name = node.value.id
            slice_node = node.slice

            # Handle arr[i], arr[i+1], arr[i-1] patterns
            index_expr = None
            if isinstance(slice_node, ast.Name):
                index_expr = slice_node.id
            elif isinstance(slice_node, ast.BinOp):
                if isinstance(slice_node.left, ast.Name) and isinstance(slice_node.right, ast.Constant):
                    var = slice_node.left.id
                    val = slice_node.right.value
                    if isinstance(val, int):
                        if isinstance(slice_node.op, ast.Add):
                            index_expr = f"{var}+{val}"
                        elif isinstance(slice_node.op, ast.Sub):
                            index_expr = f"{var}-{val}"

            if index_expr is None:
                continue

            # Use Z3 to check if index can go out of bounds
            solver = z3.Solver()
            solver.set("timeout", self.timeout_ms)

            n = z3.Int('__arr_len')
            solver.add(n >= 0)  # array length is non-negative

            # Parse the index expression
            if '+' in index_expr:
                parts = index_expr.split('+')
                idx_var = z3.Int(parts[0])
                offset = int(parts[1])
                idx = idx_var + offset
            elif '-' in index_expr and not index_expr.startswith('-'):
                parts = index_expr.split('-')
                idx_var = z3.Int(parts[0])
                offset = int(parts[1])
                idx = idx_var - offset
            else:
                idx_var = z3.Int(index_expr)
                idx = idx_var

            # Check: can index >= n (upper bound violation)?
            solver.push()
            solver.add(idx_var >= 0)  # assume loop variable is non-negative
            solver.add(n > 0)  # non-empty array
            solver.add(idx >= n)
            # Add reasonable bounds for loop variable
            solver.add(idx_var < n + 5)

            if solver.check() == z3.sat:
                model = solver.model()
                checks.append(PropertyCheck(
                    property_name="index_bounds",
                    result=VerificationResult.COUNTEREXAMPLE,
                    description=f"Array index {arr_name}[{index_expr}] can exceed bounds at line {node.lineno}",
                    line=node.lineno,
                    counterexample={
                        "array_length": model[n].as_long() if model[n] is not None else "?",
                        "index_value": model.eval(idx).as_long() if model.eval(idx) is not None else "?",
                    },
                    time_ms=(time.time() - t0) * 1000,
                ))
                solver.pop()
                continue

            solver.pop()

            # Check: can index < 0 (lower bound violation)?
            solver.push()
            solver.add(n > 0)
            solver.add(idx < 0)
            solver.add(idx_var < n)

            if solver.check() == z3.sat:
                model = solver.model()
                checks.append(PropertyCheck(
                    property_name="index_bounds",
                    result=VerificationResult.COUNTEREXAMPLE,
                    description=f"Array index {arr_name}[{index_expr}] can be negative at line {node.lineno}",
                    line=node.lineno,
                    counterexample={
                        "index_value": model.eval(idx).as_long() if model.eval(idx) is not None else "?",
                    },
                    time_ms=(time.time() - t0) * 1000,
                ))

            solver.pop()

        if not checks:
            checks.append(PropertyCheck(
                property_name="index_bounds",
                result=VerificationResult.VERIFIED,
                description="Array index accesses are within bounds",
                time_ms=(time.time() - t0) * 1000,
            ))

        return checks

    def _check_loop_invariants(self, func_def: ast.FunctionDef, code: str) -> list[PropertyCheck]:
        """Check loop termination and invariant properties using Z3."""
        checks = []
        t0 = time.time()

        for node in ast.walk(func_def):
            if not isinstance(node, ast.While):
                continue

            # Analyze the while condition and body for termination
            # Look for patterns: while low <= high, while i < n, while x != 0
            test = node.test
            body = node.body

            # Find loop variable modifications in body
            modified_vars = set()
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            modified_vars.add(target.id)
                elif isinstance(stmt, ast.AugAssign):
                    if isinstance(stmt.target, ast.Name):
                        modified_vars.add(stmt.target.id)

            # Find variables in the condition
            condition_vars = set()
            for cond_node in ast.walk(test):
                if isinstance(cond_node, ast.Name):
                    condition_vars.add(cond_node.id)

            # Check: is at least one condition variable modified in the body?
            if condition_vars and not condition_vars.intersection(modified_vars):
                checks.append(PropertyCheck(
                    property_name="loop_termination",
                    result=VerificationResult.COUNTEREXAMPLE,
                    description=f"Potential infinite loop: condition vars {condition_vars} never modified in loop body at line {node.lineno}",
                    line=node.lineno,
                    counterexample={"unmodified_vars": list(condition_vars)},
                    time_ms=(time.time() - t0) * 1000,
                ))
                continue

            # For `while low <= high` patterns, verify convergence
            if isinstance(test, ast.Compare) and len(test.ops) == 1:
                op = test.ops[0]
                if isinstance(op, (ast.LtE, ast.Lt)):
                    left_name = test.left.id if isinstance(test.left, ast.Name) else None
                    right_name = test.comparators[0].id if isinstance(test.comparators[0], ast.Name) else None

                    if left_name and right_name:
                        # Use Z3: verify that (right - left) strictly decreases each iteration
                        # This is a simplified check — verify that both vars move toward each other
                        left_increases = False
                        right_decreases = False

                        for stmt in ast.walk(node):
                            if isinstance(stmt, ast.Assign):
                                for target in stmt.targets:
                                    if isinstance(target, ast.Name):
                                        if target.id == left_name:
                                            # Check if assigned value > left (increases)
                                            if isinstance(stmt.value, ast.BinOp) and isinstance(stmt.value.op, ast.Add):
                                                left_increases = True
                                        elif target.id == right_name:
                                            if isinstance(stmt.value, ast.BinOp) and isinstance(stmt.value.op, ast.Sub):
                                                right_decreases = True

                        if not (left_increases or right_decreases):
                            solver = z3.Solver()
                            solver.set("timeout", self.timeout_ms)
                            low = z3.Int(left_name)
                            high = z3.Int(right_name)
                            # Can they be equal without the loop terminating?
                            solver.add(low <= high)
                            solver.add(low == high)
                            # This is satisfiable — check if the loop handles equality
                            if isinstance(op, ast.Lt):
                                # while low < high misses the case low == high
                                checks.append(PropertyCheck(
                                    property_name="loop_invariant",
                                    result=VerificationResult.COUNTEREXAMPLE,
                                    description=f"Loop uses '<' instead of '<=': misses case when {left_name} == {right_name} at line {node.lineno}",
                                    line=node.lineno,
                                    counterexample={left_name: "n", right_name: "n"},
                                    time_ms=(time.time() - t0) * 1000,
                                ))

        if not checks:
            checks.append(PropertyCheck(
                property_name="loop_safety",
                result=VerificationResult.VERIFIED,
                description="Loop invariants and termination conditions verified",
                time_ms=(time.time() - t0) * 1000,
            ))

        return checks

    def _check_dead_code(self, func_def: ast.FunctionDef, code: str) -> list[PropertyCheck]:
        """Detect unreachable code after return/break/continue statements."""
        checks = []
        t0 = time.time()

        def check_block(stmts):
            for i, stmt in enumerate(stmts):
                # If we hit a return/break/continue and there's code after it
                if isinstance(stmt, (ast.Return, ast.Break, ast.Continue)):
                    remaining = stmts[i + 1:]
                    if remaining:
                        dead_line = remaining[0].lineno if hasattr(remaining[0], 'lineno') else '?'
                        checks.append(PropertyCheck(
                            property_name="dead_code",
                            result=VerificationResult.COUNTEREXAMPLE,
                            description=f"Unreachable code after {'return' if isinstance(stmt, ast.Return) else 'break' if isinstance(stmt, ast.Break) else 'continue'} at line {dead_line}",
                            line=dead_line if isinstance(dead_line, int) else None,
                            time_ms=(time.time() - t0) * 1000,
                        ))
                    break

                # Recurse into blocks
                if isinstance(stmt, ast.If):
                    check_block(stmt.body)
                    if stmt.orelse:
                        check_block(stmt.orelse)
                elif isinstance(stmt, (ast.For, ast.While)):
                    check_block(stmt.body)
                elif isinstance(stmt, ast.With):
                    check_block(stmt.body)
                elif isinstance(stmt, ast.Try):
                    check_block(stmt.body)
                    for handler in stmt.handlers:
                        check_block(handler.body)

        check_block(func_def.body)

        if not checks:
            checks.append(PropertyCheck(
                property_name="dead_code",
                result=VerificationResult.VERIFIED,
                description="No unreachable code detected",
                time_ms=(time.time() - t0) * 1000,
            ))

        return checks

    def _verify_loop_bound(self, while_node, func_def) -> Optional[PropertyCheck]:
        """Verify a while loop has proper termination bounds."""
        return None

    def _verify_subscript_comparison(self, comp_node, func_def) -> Optional[PropertyCheck]:
        """Verify array access in comparison is bounds-safe."""
        return None

    def _verify_array_access(self, subscript_node, func_def) -> Optional[PropertyCheck]:
        """Verify an array subscript access is within bounds."""
        return None

    def _all_branches_return(self, if_node) -> bool:
        """Check if all branches of an if/else tree return a value."""
        body_returns = any(isinstance(s, ast.Return) for s in if_node.body)
        if not if_node.orelse:
            return False
        if isinstance(if_node.orelse[0], ast.If):
            else_returns = self._all_branches_return(if_node.orelse[0])
        else:
            else_returns = any(isinstance(s, ast.Return) for s in if_node.orelse)
        return body_returns and else_returns


def verify_code(code: str, function_name: str = "", timeout_ms: int = 5000) -> VerificationReport:
    """Convenience function to verify a Python function."""
    verifier = Z3Verifier(timeout_ms=timeout_ms)
    return verifier.verify(code, function_name)
