"""
Symbolic Executor for Sequent.

Walks Python AST functions statement-by-statement, maintaining a symbolic state
(dict mapping variable names to Z3 expressions). Produces a SymbolicState that
downstream property verifiers consume to check division-by-zero, array bounds,
overflow, and None-return issues.
"""

import ast
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import z3


class ExecStatus(Enum):
    OK = "ok"
    UNSUPPORTED = "unsupported"
    RETURNED = "returned"


@dataclass
class SymbolicState:
    """Result of symbolically executing a function."""

    variables: dict[str, Any] = field(default_factory=dict)
    path_constraints: list[Any] = field(default_factory=list)
    return_expr: Optional[Any] = None
    array_accesses: list[tuple[str, Any, int]] = field(default_factory=list)
    divisions: list[tuple[Any, int]] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    status: ExecStatus = ExecStatus.OK

    def copy(self) -> "SymbolicState":
        return SymbolicState(
            variables=dict(self.variables),
            path_constraints=list(self.path_constraints),
            return_expr=self.return_expr,
            array_accesses=list(self.array_accesses),
            divisions=list(self.divisions),
            assumptions=list(self.assumptions),
            status=self.status,
        )


class SymbolicExecutor:
    """Walk a Python AST function and build Z3 symbolic state."""

    def __init__(self, max_loop_unroll: int = 5):
        self.max_loop_unroll = max_loop_unroll
        self._counter = 0  # unique name counter

    def _fresh(self, prefix: str = "tmp") -> str:
        self._counter += 1
        return f"__{prefix}_{self._counter}"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def execute(self, func_def: ast.FunctionDef) -> SymbolicState:
        """Symbolically execute *func_def* and return the resulting state."""
        state = SymbolicState()

        # Create symbolic variables for each parameter
        for arg in func_def.args.args:
            name = arg.arg
            state.variables[name] = z3.Int(name)

        try:
            self._exec_body(func_def.body, state)
        except _UnsupportedConstruct as exc:
            state.status = ExecStatus.UNSUPPORTED
            state.assumptions.append(f"Unsupported construct: {exc}")
        except Exception as exc:
            state.status = ExecStatus.UNSUPPORTED
            state.assumptions.append(f"Execution error: {exc}")

        return state

    # ------------------------------------------------------------------
    # Statement dispatch
    # ------------------------------------------------------------------

    def _exec_body(self, stmts: list[ast.stmt], state: SymbolicState) -> None:
        for stmt in stmts:
            if state.status == ExecStatus.RETURNED:
                return
            self._exec_stmt(stmt, state)

    def _exec_stmt(self, node: ast.stmt, state: SymbolicState) -> None:
        if isinstance(node, ast.Assign):
            self._exec_assign(node, state)
        elif isinstance(node, ast.AugAssign):
            self._exec_aug_assign(node, state)
        elif isinstance(node, ast.Return):
            self._exec_return(node, state)
        elif isinstance(node, ast.If):
            self._exec_if(node, state)
        elif isinstance(node, ast.While):
            self._exec_while(node, state)
        elif isinstance(node, ast.For):
            self._exec_for(node, state)
        elif isinstance(node, ast.Expr):
            # Expression statement (e.g. function call) -- skip side effects
            pass
        elif isinstance(node, ast.Pass):
            pass
        else:
            state.assumptions.append(
                f"Skipped unsupported statement: {type(node).__name__} at line {getattr(node, 'lineno', '?')}"
            )

    # ------------------------------------------------------------------
    # Assign / AugAssign
    # ------------------------------------------------------------------

    def _exec_assign(self, node: ast.Assign, state: SymbolicState) -> None:
        rhs = self._eval_expr(node.value, state, getattr(node, "lineno", 0))
        for target in node.targets:
            if isinstance(target, ast.Name):
                state.variables[target.id] = rhs
            elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
                # Tuple/list unpacking -- create symbolic vars
                for i, elt in enumerate(target.elts):
                    if isinstance(elt, ast.Name):
                        state.variables[elt.id] = z3.Int(self._fresh(elt.id))
                        state.assumptions.append(f"Unpacking target {elt.id} approximated")
            else:
                state.assumptions.append(f"Unsupported assign target: {type(target).__name__}")

    def _exec_aug_assign(self, node: ast.AugAssign, state: SymbolicState) -> None:
        if not isinstance(node.target, ast.Name):
            state.assumptions.append("AugAssign to non-Name target skipped")
            return
        name = node.target.id
        lineno = getattr(node, "lineno", 0)
        current = state.variables.get(name, z3.Int(name))
        rhs = self._eval_expr(node.value, state, lineno)
        result = self._apply_binop(node.op, current, rhs, lineno, state)
        state.variables[name] = result

    # ------------------------------------------------------------------
    # Return
    # ------------------------------------------------------------------

    def _exec_return(self, node: ast.Return, state: SymbolicState) -> None:
        if node.value is not None:
            state.return_expr = self._eval_expr(node.value, state, getattr(node, "lineno", 0))
        else:
            state.return_expr = None
        state.status = ExecStatus.RETURNED

    # ------------------------------------------------------------------
    # If / Else
    # ------------------------------------------------------------------

    def _exec_if(self, node: ast.If, state: SymbolicState) -> None:
        lineno = getattr(node, "lineno", 0)
        try:
            cond = self._eval_expr(node.test, state, lineno)
        except _UnsupportedConstruct:
            state.assumptions.append(f"Condition at line {lineno} not supported, exploring both branches")
            # Execute the then-branch only as approximation
            self._exec_body(node.body, state)
            return

        # Fork: true branch
        true_state = state.copy()
        true_state.path_constraints.append(cond)
        self._exec_body(node.body, true_state)

        # Fork: false branch
        false_state = state.copy()
        false_state.path_constraints.append(z3.Not(cond))
        if node.orelse:
            self._exec_body(node.orelse, false_state)

        # Merge: collect artifacts from both branches
        state.array_accesses = true_state.array_accesses + false_state.array_accesses
        state.divisions = true_state.divisions + false_state.divisions
        state.assumptions = true_state.assumptions + false_state.assumptions

        # If both returned, pick the true branch return (caller will see RETURNED)
        if true_state.status == ExecStatus.RETURNED and false_state.status == ExecStatus.RETURNED:
            # Use Z3 If to merge return expressions
            if true_state.return_expr is not None and false_state.return_expr is not None:
                try:
                    state.return_expr = z3.If(cond, true_state.return_expr, false_state.return_expr)
                except Exception:
                    state.return_expr = true_state.return_expr
            else:
                state.return_expr = true_state.return_expr
            state.status = ExecStatus.RETURNED
            return

        if true_state.status == ExecStatus.RETURNED:
            # Only true branch returned -- continue with false state
            state.variables = false_state.variables
            state.path_constraints = false_state.path_constraints
            # Record return from the true branch for analysis
            if state.return_expr is None:
                state.return_expr = true_state.return_expr
            return

        if false_state.status == ExecStatus.RETURNED:
            state.variables = true_state.variables
            state.path_constraints = true_state.path_constraints
            if state.return_expr is None:
                state.return_expr = false_state.return_expr
            return

        # Neither returned -- merge variables with Z3 If
        all_vars = set(true_state.variables) | set(false_state.variables)
        for v in all_vars:
            t_val = true_state.variables.get(v)
            f_val = false_state.variables.get(v)
            if t_val is not None and f_val is not None:
                try:
                    state.variables[v] = z3.If(cond, t_val, f_val)
                except Exception:
                    state.variables[v] = t_val
            elif t_val is not None:
                state.variables[v] = t_val
            elif f_val is not None:
                state.variables[v] = f_val

        state.path_constraints = list(set(true_state.path_constraints) | set(false_state.path_constraints))

    # ------------------------------------------------------------------
    # While (unrolled)
    # ------------------------------------------------------------------

    def _exec_while(self, node: ast.While, state: SymbolicState) -> None:
        lineno = getattr(node, "lineno", 0)
        for _ in range(self.max_loop_unroll):
            if state.status == ExecStatus.RETURNED:
                return
            try:
                cond = self._eval_expr(node.test, state, lineno)
            except _UnsupportedConstruct:
                state.assumptions.append(f"While condition at line {lineno} unsupported")
                return
            state.path_constraints.append(cond)
            self._exec_body(node.body, state)

        state.assumptions.append(f"While loop at line {lineno} unrolled {self.max_loop_unroll} times")

    # ------------------------------------------------------------------
    # For (range-based unrolling)
    # ------------------------------------------------------------------

    def _exec_for(self, node: ast.For, state: SymbolicState) -> None:
        lineno = getattr(node, "lineno", 0)

        if not isinstance(node.target, ast.Name):
            state.assumptions.append(f"For with non-Name target at line {lineno}")
            return

        loop_var = node.target.id

        # Try to interpret range(...)
        if (isinstance(node.iter, ast.Call)
                and isinstance(node.iter.func, ast.Name)
                and node.iter.func.id == "range"):
            args = node.iter.args
            try:
                start, stop, step = self._parse_range_args(args, state, lineno)
            except _UnsupportedConstruct:
                state.assumptions.append(f"For-range args at line {lineno} unsupported, using symbolic unroll")
                # Fallback: symbolic loop variable
                state.variables[loop_var] = z3.Int(loop_var)
                for _ in range(self.max_loop_unroll):
                    if state.status == ExecStatus.RETURNED:
                        return
                    self._exec_body(node.body, state)
                return

            # Unroll the range loop
            iterations = 0
            current = start
            for _ in range(self.max_loop_unroll * 10):  # generous limit for concrete ranges
                if iterations >= self.max_loop_unroll:
                    state.assumptions.append(f"For loop at line {lineno} capped at {self.max_loop_unroll} iterations")
                    break
                # If start/stop are concrete ints, compare directly
                if isinstance(current, int) and isinstance(stop, int):
                    if (step > 0 and current >= stop) or (step < 0 and current <= stop):
                        break
                    state.variables[loop_var] = z3.IntVal(current)
                    self._exec_body(node.body, state)
                    if state.status == ExecStatus.RETURNED:
                        return
                    current += step
                    iterations += 1
                else:
                    # Symbolic bounds -- treat as while-style unroll
                    state.variables[loop_var] = z3.Int(self._fresh(loop_var))
                    self._exec_body(node.body, state)
                    if state.status == ExecStatus.RETURNED:
                        return
                    iterations += 1
            return

        # Not a range-based for -- approximate
        state.variables[loop_var] = z3.Int(loop_var)
        state.assumptions.append(f"Non-range for loop at line {lineno} approximated")
        for _ in range(self.max_loop_unroll):
            if state.status == ExecStatus.RETURNED:
                return
            self._exec_body(node.body, state)

    def _parse_range_args(self, args, state, lineno):
        """Parse range() arguments into (start, stop, step)."""
        if len(args) == 1:
            stop = self._eval_range_bound(args[0], state, lineno)
            return 0, stop, 1
        elif len(args) == 2:
            start = self._eval_range_bound(args[0], state, lineno)
            stop = self._eval_range_bound(args[1], state, lineno)
            return start, stop, 1
        elif len(args) == 3:
            start = self._eval_range_bound(args[0], state, lineno)
            stop = self._eval_range_bound(args[1], state, lineno)
            step = self._eval_range_bound(args[2], state, lineno)
            return start, stop, step
        raise _UnsupportedConstruct("range() with unexpected arg count")

    def _eval_range_bound(self, node, state, lineno):
        """Try to get a concrete int for a range bound, fall back to Z3 expr."""
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        # Return a Z3 expression
        return self._eval_expr(node, state, lineno)

    # ------------------------------------------------------------------
    # Expression evaluation → Z3 expression
    # ------------------------------------------------------------------

    def _eval_expr(self, node: ast.expr, state: SymbolicState, lineno: int) -> Any:
        if isinstance(node, ast.Constant):
            return self._eval_constant(node)
        elif isinstance(node, ast.Name):
            return self._eval_name(node, state)
        elif isinstance(node, ast.BinOp):
            return self._eval_binop(node, state, lineno)
        elif isinstance(node, ast.Compare):
            return self._eval_compare(node, state, lineno)
        elif isinstance(node, ast.BoolOp):
            return self._eval_boolop(node, state, lineno)
        elif isinstance(node, ast.UnaryOp):
            return self._eval_unaryop(node, state, lineno)
        elif isinstance(node, ast.Call):
            return self._eval_call(node, state, lineno)
        elif isinstance(node, ast.Subscript):
            return self._eval_subscript(node, state, lineno)
        elif isinstance(node, ast.IfExp):
            return self._eval_ifexp(node, state, lineno)
        elif isinstance(node, ast.NameConstant):  # Python 3.7 compat
            return self._eval_constant_value(node.value)
        else:
            raise _UnsupportedConstruct(f"Expression type {type(node).__name__} at line {lineno}")

    def _eval_constant(self, node: ast.Constant) -> Any:
        return self._eval_constant_value(node.value)

    def _eval_constant_value(self, value) -> Any:
        if isinstance(value, bool):
            return z3.BoolVal(value)
        elif isinstance(value, int):
            return z3.IntVal(value)
        elif isinstance(value, float):
            return z3.RealVal(value)
        elif value is None:
            # Represent None as a special integer sentinel
            return z3.IntVal(-999999)
        else:
            raise _UnsupportedConstruct(f"Constant type {type(value).__name__}")

    def _eval_name(self, node: ast.Name, state: SymbolicState) -> Any:
        name = node.id
        if name in state.variables:
            return state.variables[name]
        if name == "True":
            return z3.BoolVal(True)
        if name == "False":
            return z3.BoolVal(False)
        if name == "None":
            return z3.IntVal(-999999)
        # Unknown variable -- create fresh symbolic var
        var = z3.Int(name)
        state.variables[name] = var
        return var

    def _eval_binop(self, node: ast.BinOp, state: SymbolicState, lineno: int) -> Any:
        left = self._eval_expr(node.left, state, lineno)
        right = self._eval_expr(node.right, state, lineno)
        return self._apply_binop(node.op, left, right, lineno, state)

    def _apply_binop(self, op, left, right, lineno: int, state: SymbolicState) -> Any:
        if isinstance(op, ast.Add):
            return left + right
        elif isinstance(op, ast.Sub):
            return left - right
        elif isinstance(op, ast.Mult):
            return left * right
        elif isinstance(op, ast.FloorDiv):
            state.divisions.append((right, lineno))
            return left / right  # Z3 integer division
        elif isinstance(op, ast.Div):
            state.divisions.append((right, lineno))
            return left / right
        elif isinstance(op, ast.Mod):
            state.divisions.append((right, lineno))
            return left % right
        elif isinstance(op, ast.Pow):
            # Z3 doesn't support general exponentiation -- approximate
            if z3.is_int_value(right):
                exp = right.as_long()
                if 0 <= exp <= 10:
                    result = z3.IntVal(1)
                    for _ in range(exp):
                        result = result * left
                    return result
            state.assumptions.append(f"Power operation at line {lineno} approximated")
            return z3.Int(self._fresh("pow"))
        elif isinstance(op, ast.BitAnd):
            return left & right
        elif isinstance(op, ast.BitOr):
            return left | right
        elif isinstance(op, ast.LShift):
            state.assumptions.append(f"Left shift at line {lineno} approximated")
            return z3.Int(self._fresh("lshift"))
        elif isinstance(op, ast.RShift):
            state.assumptions.append(f"Right shift at line {lineno} approximated")
            return z3.Int(self._fresh("rshift"))
        else:
            raise _UnsupportedConstruct(f"BinOp {type(op).__name__} at line {lineno}")

    def _eval_compare(self, node: ast.Compare, state: SymbolicState, lineno: int) -> Any:
        left = self._eval_expr(node.left, state, lineno)
        constraints = []
        for op, comparator in zip(node.ops, node.comparators):
            right = self._eval_expr(comparator, state, lineno)
            constraints.append(self._apply_cmp(op, left, right, lineno))
            left = right
        if len(constraints) == 1:
            return constraints[0]
        return z3.And(*constraints)

    def _apply_cmp(self, op, left, right, lineno: int) -> Any:
        if isinstance(op, ast.Lt):
            return left < right
        elif isinstance(op, ast.LtE):
            return left <= right
        elif isinstance(op, ast.Gt):
            return left > right
        elif isinstance(op, ast.GtE):
            return left >= right
        elif isinstance(op, ast.Eq):
            return left == right
        elif isinstance(op, ast.NotEq):
            return left != right
        elif isinstance(op, ast.Is):
            return left == right
        elif isinstance(op, ast.IsNot):
            return left != right
        elif isinstance(op, ast.In):
            # Approximate: return unconstrained bool
            return z3.Bool(self._fresh("in"))
        elif isinstance(op, ast.NotIn):
            return z3.Bool(self._fresh("notin"))
        else:
            raise _UnsupportedConstruct(f"Compare op {type(op).__name__} at line {lineno}")

    def _eval_boolop(self, node: ast.BoolOp, state: SymbolicState, lineno: int) -> Any:
        values = [self._eval_expr(v, state, lineno) for v in node.values]
        if isinstance(node.op, ast.And):
            return z3.And(*values)
        elif isinstance(node.op, ast.Or):
            return z3.Or(*values)
        else:
            raise _UnsupportedConstruct(f"BoolOp {type(node.op).__name__}")

    def _eval_unaryop(self, node: ast.UnaryOp, state: SymbolicState, lineno: int) -> Any:
        operand = self._eval_expr(node.operand, state, lineno)
        if isinstance(node.op, ast.Not):
            return z3.Not(operand)
        elif isinstance(node.op, ast.USub):
            return -operand
        elif isinstance(node.op, ast.UAdd):
            return operand
        elif isinstance(node.op, ast.Invert):
            return ~operand
        else:
            raise _UnsupportedConstruct(f"UnaryOp {type(node.op).__name__}")

    def _eval_call(self, node: ast.Call, state: SymbolicState, lineno: int) -> Any:
        # Handle len()
        if isinstance(node.func, ast.Name) and node.func.id == "len" and len(node.args) == 1:
            arg = node.args[0]
            if isinstance(arg, ast.Name):
                len_name = f"len_{arg.id}"
                if len_name not in state.variables:
                    len_var = z3.Int(len_name)
                    state.variables[len_name] = len_var
                    # len is non-negative
                    state.path_constraints.append(len_var >= 0)
                return state.variables[len_name]

        # Handle abs()
        if isinstance(node.func, ast.Name) and node.func.id == "abs" and len(node.args) == 1:
            val = self._eval_expr(node.args[0], state, lineno)
            return z3.If(val >= 0, val, -val)

        # Handle min/max with 2 args
        if isinstance(node.func, ast.Name) and node.func.id in ("min", "max") and len(node.args) == 2:
            a = self._eval_expr(node.args[0], state, lineno)
            b = self._eval_expr(node.args[1], state, lineno)
            if node.func.id == "min":
                return z3.If(a <= b, a, b)
            else:
                return z3.If(a >= b, a, b)

        # Unsupported call -- return fresh symbolic variable
        state.assumptions.append(f"Call to {ast.dump(node.func)} at line {lineno} approximated")
        return z3.Int(self._fresh("call"))

    def _eval_subscript(self, node: ast.Subscript, state: SymbolicState, lineno: int) -> Any:
        # Get array name
        if isinstance(node.value, ast.Name):
            arr_name = node.value.id
        else:
            arr_name = self._fresh("arr")

        # Get index expression
        slice_node = node.slice
        # Handle Index wrapper (Python 3.8 compat)
        if isinstance(slice_node, ast.Index):
            slice_node = slice_node.value

        index_expr = self._eval_expr(slice_node, state, lineno)

        # Record array access for bounds checking
        state.array_accesses.append((arr_name, index_expr, lineno))

        # Model array as a Z3 Function (Array)
        arr_func_name = f"__arr_{arr_name}"
        if arr_func_name not in state.variables:
            arr_func = z3.Function(arr_func_name, z3.IntSort(), z3.IntSort())
            state.variables[arr_func_name] = arr_func
        else:
            arr_func = state.variables[arr_func_name]

        return arr_func(index_expr)

    def _eval_ifexp(self, node: ast.IfExp, state: SymbolicState, lineno: int) -> Any:
        cond = self._eval_expr(node.test, state, lineno)
        true_val = self._eval_expr(node.body, state, lineno)
        false_val = self._eval_expr(node.orelse, state, lineno)
        return z3.If(cond, true_val, false_val)


class _UnsupportedConstruct(Exception):
    """Raised when we encounter a construct we cannot translate to Z3."""
    pass
