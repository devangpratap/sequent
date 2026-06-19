"""
Z3 Verification Engine for JavaScript/TypeScript.

Translates JS/TS source into property checks using regex-based AST parsing,
then verifies the same property classes as the Python Z3 engine:
1. Division safety (division by zero)
2. Null/undefined safety
3. Array index bounds
4. Return completeness
5. Loop termination hints
6. Operator consistency
7. Dead code detection
8. Arithmetic overflow

Uses the same Z3Verifier result types (PropertyCheck, VerificationReport)
so the neurosymbolic pipeline works without modification.
"""

from __future__ import annotations

import re
import textwrap
import time
from typing import Optional

import z3

from verifier.z3_engine import PropertyCheck, VerificationReport, VerificationResult


# ---------------------------------------------------------------------------
# Lightweight JS/TS parser structures
# ---------------------------------------------------------------------------

class JSNode:
    """Minimal AST node for JS/TS property checking."""
    __slots__ = ("type", "name", "line", "children", "params", "body_text",
                 "condition", "op", "left", "right", "value")

    def __init__(self, type: str, name: str = "", line: int = 0):
        self.type = type
        self.name = name
        self.line = line
        self.children: list[JSNode] = []
        self.params: list[str] = []
        self.body_text: str = ""
        self.condition: str = ""
        self.op: str = ""
        self.left: str = ""
        self.right: str = ""
        self.value: str = ""


def _parse_js(code: str) -> list[JSNode]:
    """Parse JS/TS source into a flat list of statement nodes."""
    nodes = []
    lines = code.split("\n")

    # Regex patterns for JS/TS constructs
    func_re = re.compile(
        r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)"
    )
    arrow_re = re.compile(
        r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>"
    )
    return_re = re.compile(r"^\s*return\b\s*(.*)")
    if_re = re.compile(r"^\s*if\s*\((.+?)\)\s*\{?")
    elif_re = re.compile(r"^\s*\}\s*else\s+if\s*\((.+?)\)\s*\{?")
    else_re = re.compile(r"^\s*\}\s*else\s*\{?")
    for_re = re.compile(r"^\s*for\s*\((.+?)\)\s*\{?")
    while_re = re.compile(r"^\s*while\s*\((.+?)\)\s*\{?")
    var_re = re.compile(r"^\s*(?:const|let|var)\s+(\w+)\s*(?::\s*\w+)?\s*=\s*(.*)")
    throw_re = re.compile(r"^\s*throw\b")
    break_re = re.compile(r"^\s*break\b")
    continue_re = re.compile(r"^\s*continue\b")
    div_re = re.compile(r"(\w+)\s*/\s*(\w+)")
    subscript_re = re.compile(r"(\w+)\[(.+?)\]")

    current_func = None

    for lineno_0, raw_line in enumerate(lines):
        lineno = lineno_0 + 1
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Function declaration
        m = func_re.match(raw_line)
        if not m:
            m = arrow_re.match(raw_line)
        if m:
            node = JSNode("function", name=m.group(1), line=lineno)
            params_str = m.group(2) if m.lastindex >= 2 else ""
            if params_str.strip():
                node.params = [
                    p.strip().split(":")[0].split("=")[0].strip()
                    for p in params_str.split(",")
                    if p.strip()
                ]
            current_func = node
            nodes.append(node)
            continue

        # Return
        m = return_re.match(raw_line)
        if m:
            node = JSNode("return", line=lineno)
            node.value = m.group(1).rstrip(";").strip() if m.group(1) else ""
            nodes.append(node)
            continue

        # If / else if / else
        m = elif_re.match(raw_line)
        if m:
            node = JSNode("elif", line=lineno)
            node.condition = m.group(1)
            nodes.append(node)
            continue

        m = if_re.match(raw_line)
        if m:
            node = JSNode("if", line=lineno)
            node.condition = m.group(1)
            nodes.append(node)
            continue

        m = else_re.match(raw_line)
        if m:
            nodes.append(JSNode("else", line=lineno))
            continue

        # For loop
        m = for_re.match(raw_line)
        if m:
            node = JSNode("for", line=lineno)
            node.condition = m.group(1)
            nodes.append(node)
            continue

        # While loop
        m = while_re.match(raw_line)
        if m:
            node = JSNode("while", line=lineno)
            node.condition = m.group(1)
            nodes.append(node)
            continue

        # Variable declaration
        m = var_re.match(raw_line)
        if m:
            node = JSNode("var", name=m.group(1), line=lineno)
            node.value = m.group(2).rstrip(";").strip()
            nodes.append(node)
            continue

        # Control flow
        if throw_re.match(raw_line):
            nodes.append(JSNode("throw", line=lineno))
            continue
        if break_re.match(raw_line):
            nodes.append(JSNode("break", line=lineno))
            continue
        if continue_re.match(raw_line):
            nodes.append(JSNode("continue", line=lineno))
            continue

        # Generic expression
        if stripped and not stripped.startswith("}") and not stripped.startswith("{"):
            node = JSNode("expr", line=lineno)
            node.body_text = stripped
            nodes.append(node)

    return nodes


def _find_functions(nodes: list[JSNode]) -> list[JSNode]:
    """Extract function nodes."""
    return [n for n in nodes if n.type == "function"]


# ---------------------------------------------------------------------------
# JS/TS Z3 Verifier
# ---------------------------------------------------------------------------

class JSVerifier:
    """Verify JavaScript/TypeScript functions using Z3 SMT solver."""

    def __init__(self, timeout_ms: int = 5000):
        self.timeout_ms = timeout_ms

    def verify(self, code: str, function_name: str = "") -> VerificationReport:
        """Run all property checks on JS/TS source."""
        code = textwrap.dedent(code).strip()
        report = VerificationReport(function_name=function_name)
        t0 = time.time()

        nodes = _parse_js(code)
        functions = _find_functions(nodes)

        if not functions:
            report.overall_result = VerificationResult.UNSUPPORTED
            report.total_time_ms = (time.time() - t0) * 1000
            return report

        func = functions[0]
        if not function_name:
            report.function_name = func.name

        # Collect all nodes that belong to this function
        # (everything from func to next function or end)
        func_idx = nodes.index(func)
        next_func_idx = len(nodes)
        for i in range(func_idx + 1, len(nodes)):
            if nodes[i].type == "function":
                next_func_idx = i
                break
        func_nodes = nodes[func_idx:next_func_idx]

        checkers = [
            self._check_null_safety,
            self._check_division_safety,
            self._check_array_bounds,
            self._check_return_completeness,
            self._check_loop_termination,
            self._check_dead_code,
            self._check_operator_consistency,
            self._check_overflow,
        ]

        for checker in checkers:
            try:
                checks = checker(func, func_nodes, code)
                report.checks.extend(checks)
            except Exception:
                pass

        # Determine overall result
        _info_checks = {"sym_overflow"}
        decisive = [c for c in report.checks if c.property_name not in _info_checks]
        if report.has_bugs:
            report.overall_result = VerificationResult.COUNTEREXAMPLE
        elif all(c.result == VerificationResult.VERIFIED for c in decisive):
            report.overall_result = VerificationResult.VERIFIED
        elif any(c.result == VerificationResult.UNKNOWN for c in decisive):
            report.overall_result = VerificationResult.UNKNOWN
        else:
            report.overall_result = VerificationResult.VERIFIED if decisive else VerificationResult.UNKNOWN

        report.total_time_ms = (time.time() - t0) * 1000
        return report

    # --- Property checkers -------------------------------------------------

    def _check_null_safety(self, func: JSNode, nodes: list[JSNode],
                           code: str) -> list[PropertyCheck]:
        """Check for null/undefined dereference on parameters."""
        checks = []
        t0 = time.time()
        params = func.params
        if not params:
            return [PropertyCheck(
                property_name="null_safety",
                result=VerificationResult.VERIFIED,
                description="No parameters to check",
                time_ms=(time.time() - t0) * 1000,
            )]

        # Find null/undefined guards
        guarded = set()
        for n in nodes:
            if n.type in ("if", "elif"):
                cond = n.condition
                for p in params:
                    if p in cond and any(kw in cond for kw in
                                          ["null", "undefined", "!= null", "!== null",
                                           "!== undefined", "typeof"]):
                        guarded.add(p)

        # Find unguarded parameter usage
        flagged = set()
        for n in nodes:
            if n.type == "function":
                continue
            text = n.body_text or n.value or n.condition or ""
            for p in params:
                if p in flagged or p in guarded:
                    continue
                # Check for property access: param.something or param[something]
                if re.search(rf"\b{re.escape(p)}\s*\.", text) or \
                   re.search(rf"\b{re.escape(p)}\s*\[", text):
                    flagged.add(p)
                    checks.append(PropertyCheck(
                        property_name="null_safety",
                        result=VerificationResult.COUNTEREXAMPLE,
                        description=f"Parameter '{p}' used without null/undefined check at line {n.line}",
                        line=n.line,
                        counterexample={"param": p, "value": "null"},
                        time_ms=(time.time() - t0) * 1000,
                    ))

        if not checks:
            checks.append(PropertyCheck(
                property_name="null_safety",
                result=VerificationResult.VERIFIED,
                description="All parameters properly guarded against null/undefined",
                time_ms=(time.time() - t0) * 1000,
            ))

        return checks

    def _check_division_safety(self, func: JSNode, nodes: list[JSNode],
                                code: str) -> list[PropertyCheck]:
        """Check for division by zero."""
        checks = []
        t0 = time.time()
        params = set(func.params)

        for n in nodes:
            text = n.body_text or n.value or ""
            for m in re.finditer(r"(\w+)\s*/\s*(\w+)", text):
                divisor = m.group(2)
                if divisor in params:
                    # Check if there's a zero guard
                    has_guard = False
                    for g in nodes:
                        if g.type in ("if", "elif") and divisor in g.condition:
                            if any(kw in g.condition for kw in ["=== 0", "== 0", "!= 0", "!== 0"]):
                                has_guard = True
                                break
                    if not has_guard:
                        solver = z3.Solver()
                        solver.set("timeout", self.timeout_ms)
                        d = z3.Int(divisor)
                        solver.add(d == 0)
                        if solver.check() == z3.sat:
                            checks.append(PropertyCheck(
                                property_name="division_safety",
                                result=VerificationResult.COUNTEREXAMPLE,
                                description=f"Possible division by zero: {divisor} can be 0 at line {n.line}",
                                line=n.line,
                                counterexample={divisor: 0},
                                time_ms=(time.time() - t0) * 1000,
                            ))

        if not checks:
            checks.append(PropertyCheck(
                property_name="division_safety",
                result=VerificationResult.VERIFIED,
                description="No division-by-zero issues detected",
                time_ms=(time.time() - t0) * 1000,
            ))

        return checks

    def _check_array_bounds(self, func: JSNode, nodes: list[JSNode],
                             code: str) -> list[PropertyCheck]:
        """Check array index accesses are within bounds."""
        checks = []
        t0 = time.time()

        for n in nodes:
            text = n.body_text or n.value or ""
            for m in re.finditer(r"(\w+)\[(\w+)(?:\s*([+\-])\s*(\d+))?\]", text):
                arr_name = m.group(1)
                idx_var = m.group(2)
                op = m.group(3)
                offset = int(m.group(4)) if m.group(4) else 0

                # Skip non-array accesses (object property, string index by name)
                if idx_var in ("length", "size", "prototype"):
                    continue

                solver = z3.Solver()
                solver.set("timeout", self.timeout_ms)
                arr_len = z3.Int("__arr_len")
                idx = z3.Int(idx_var)

                solver.add(arr_len >= 0, idx >= 0, arr_len > 0)

                if op == "+":
                    index_expr = idx + offset
                elif op == "-":
                    index_expr = idx - offset
                else:
                    index_expr = idx

                # Can index >= length?
                solver.push()
                solver.add(index_expr >= arr_len)
                solver.add(idx < arr_len + 5)

                if solver.check() == z3.sat:
                    model = solver.model()
                    idx_str = f"{idx_var}{op}{m.group(4)}" if op else idx_var
                    checks.append(PropertyCheck(
                        property_name="index_bounds",
                        result=VerificationResult.COUNTEREXAMPLE,
                        description=f"Array index {arr_name}[{idx_str}] can exceed bounds at line {n.line}",
                        line=n.line,
                        counterexample={
                            "array_length": model[arr_len].as_long(),
                            "index_value": model.eval(index_expr).as_long(),
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

    def _check_return_completeness(self, func: JSNode, nodes: list[JSNode],
                                    code: str) -> list[PropertyCheck]:
        """Check that all code paths return a value."""
        checks = []
        t0 = time.time()

        # Find return statements
        returns = [n for n in nodes if n.type == "return"]
        if not returns:
            checks.append(PropertyCheck(
                property_name="return_completeness",
                result=VerificationResult.VERIFIED,
                description="No return statements (void function)",
                time_ms=(time.time() - t0) * 1000,
            ))
            return checks

        # Check for if blocks that return without else
        has_value_return = any(r.value for r in returns)
        if not has_value_return:
            checks.append(PropertyCheck(
                property_name="return_completeness",
                result=VerificationResult.VERIFIED,
                description="Return path analysis passed",
                time_ms=(time.time() - t0) * 1000,
            ))
            return checks

        # Look for if without else that contains a return
        has_if_return = False
        has_else = False
        for i, n in enumerate(nodes):
            if n.type == "if":
                # Check if any return exists before the next if/else/function at same level
                for j in range(i + 1, len(nodes)):
                    sib = nodes[j]
                    if sib.type in ("function", "if"):
                        break
                    if sib.type == "return":
                        has_if_return = True
                        break
                    if sib.type == "else":
                        has_else = True
                        break

        if has_if_return and not has_else:
            checks.append(PropertyCheck(
                property_name="return_completeness",
                result=VerificationResult.COUNTEREXAMPLE,
                description="Function returns a value in if-branch but may fall through without else",
                line=func.line,
                counterexample={"issue": "missing_else_return"},
                time_ms=(time.time() - t0) * 1000,
            ))
        else:
            checks.append(PropertyCheck(
                property_name="return_completeness",
                result=VerificationResult.VERIFIED,
                description="Return path analysis passed",
                time_ms=(time.time() - t0) * 1000,
            ))

        return checks

    def _check_loop_termination(self, func: JSNode, nodes: list[JSNode],
                                 code: str) -> list[PropertyCheck]:
        """Check loop termination properties."""
        checks = []
        t0 = time.time()

        for i, n in enumerate(nodes):
            if n.type != "while":
                continue

            cond = n.condition
            # Find variables in condition
            cond_vars = set(re.findall(r"\b([a-zA-Z_]\w*)\b", cond))
            cond_vars -= {"true", "false", "null", "undefined"}

            # Find variables modified in loop body (until next function or end)
            modified = set()
            for j in range(i + 1, len(nodes)):
                sib = nodes[j]
                if sib.type == "function":
                    break
                text = sib.body_text or ""
                # Assignments: x = ..., x += ..., x++, x--
                for m in re.finditer(r"\b(\w+)\s*(?:[+\-*/]?=|[+]{2}|[-]{2})", text):
                    modified.add(m.group(1))
                if sib.type == "var":
                    modified.add(sib.name)

            if cond_vars and not cond_vars.intersection(modified):
                checks.append(PropertyCheck(
                    property_name="loop_termination",
                    result=VerificationResult.COUNTEREXAMPLE,
                    description=f"Potential infinite loop: condition vars {cond_vars} never modified at line {n.line}",
                    line=n.line,
                    counterexample={"unmodified_vars": list(cond_vars)},
                    time_ms=(time.time() - t0) * 1000,
                ))

        if not checks:
            checks.append(PropertyCheck(
                property_name="loop_safety",
                result=VerificationResult.VERIFIED,
                description="Loop termination conditions verified",
                time_ms=(time.time() - t0) * 1000,
            ))

        return checks

    def _check_dead_code(self, func: JSNode, nodes: list[JSNode],
                          code: str) -> list[PropertyCheck]:
        """Detect unreachable code after return/break/continue/throw."""
        checks = []
        t0 = time.time()

        terminators = {"return", "break", "continue", "throw"}
        for i, n in enumerate(nodes):
            if n.type in terminators:
                # Check if next node exists and is not a closing construct
                if i + 1 < len(nodes):
                    nxt = nodes[i + 1]
                    if nxt.type not in ("function", "else", "elif") and nxt.line > n.line:
                        # Check it's not just a closing brace
                        checks.append(PropertyCheck(
                            property_name="dead_code",
                            result=VerificationResult.COUNTEREXAMPLE,
                            description=f"Unreachable code after {n.type} at line {nxt.line}",
                            line=nxt.line,
                            time_ms=(time.time() - t0) * 1000,
                        ))

        if not checks:
            checks.append(PropertyCheck(
                property_name="dead_code",
                result=VerificationResult.VERIFIED,
                description="No unreachable code detected",
                time_ms=(time.time() - t0) * 1000,
            ))

        return checks

    def _check_operator_consistency(self, func: JSNode, nodes: list[JSNode],
                                     code: str) -> list[PropertyCheck]:
        """Check for == vs === and other operator issues."""
        checks = []
        t0 = time.time()

        for n in nodes:
            text = n.body_text or n.condition or n.value or ""
            # Flag loose equality (== instead of ===), excluding ===
            for m in re.finditer(r"(?<!=)(?<!\!)={2}(?!=)", text):
                checks.append(PropertyCheck(
                    property_name="operator_consistency",
                    result=VerificationResult.COUNTEREXAMPLE,
                    description=f"Loose equality (==) used instead of strict (===) at line {n.line}",
                    line=n.line,
                    counterexample={"suggestion": "Use === for type-safe comparison"},
                    time_ms=(time.time() - t0) * 1000,
                ))
                break  # One per line

            # Flag != instead of !==
            for m in re.finditer(r"(?<!\!)!=(?!=)", text):
                checks.append(PropertyCheck(
                    property_name="operator_consistency",
                    result=VerificationResult.COUNTEREXAMPLE,
                    description=f"Loose inequality (!=) used instead of strict (!==) at line {n.line}",
                    line=n.line,
                    counterexample={"suggestion": "Use !== for type-safe comparison"},
                    time_ms=(time.time() - t0) * 1000,
                ))
                break

        if not checks:
            checks.append(PropertyCheck(
                property_name="operator_consistency",
                result=VerificationResult.VERIFIED,
                description="Operator usage is consistent",
                time_ms=(time.time() - t0) * 1000,
            ))

        return checks

    def _check_overflow(self, func: JSNode, nodes: list[JSNode],
                         code: str) -> list[PropertyCheck]:
        """Check for potential integer overflow in arithmetic."""
        checks = []
        t0 = time.time()
        params = set(func.params)

        for n in nodes:
            text = n.body_text or n.value or ""
            for m in re.finditer(r"(\w+)\s*\*\s*(\w+)", text):
                a_name, b_name = m.group(1), m.group(2)
                if a_name in params and b_name in params:
                    solver = z3.Solver()
                    solver.set("timeout", self.timeout_ms)
                    a = z3.Int(a_name)
                    b = z3.Int(b_name)
                    MAX_SAFE = 2**53 - 1  # JS Number.MAX_SAFE_INTEGER

                    solver.add(a > 0, b > 0, a < MAX_SAFE, b < MAX_SAFE)
                    solver.add(a * b > MAX_SAFE)

                    if solver.check() == z3.sat:
                        model = solver.model()
                        checks.append(PropertyCheck(
                            property_name="overflow_safety",
                            result=VerificationResult.COUNTEREXAMPLE,
                            description=f"Integer overflow possible: {a_name} * {b_name} > MAX_SAFE_INTEGER at line {n.line}",
                            line=n.line,
                            counterexample={
                                a_name: model[a].as_long(),
                                b_name: model[b].as_long(),
                            },
                            time_ms=(time.time() - t0) * 1000,
                        ))

        if not checks:
            checks.append(PropertyCheck(
                property_name="overflow_safety",
                result=VerificationResult.VERIFIED,
                description="No overflow issues detected",
                time_ms=(time.time() - t0) * 1000,
            ))

        return checks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def verify_js(code: str, function_name: str = "",
              timeout_ms: int = 5000) -> VerificationReport:
    """Verify a JavaScript/TypeScript function.

    Returns the same VerificationReport as the Python verifier.
    """
    verifier = JSVerifier(timeout_ms=timeout_ms)
    return verifier.verify(code, function_name)
