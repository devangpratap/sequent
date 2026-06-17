"""
Mutation Engine for Sequent.

Programmatically injects bugs into correct Python functions to generate
labeled training data for the GNN bug predictor.

Bug classes:
1. OFF_BY_ONE     — change loop bounds, index arithmetic by ±1
2. BOUNDARY_ERROR — remove or break boundary/null checks
3. WRONG_OPERATOR — swap comparison/arithmetic operators
4. NONE_DEREF     — remove None/null guard checks
5. INTEGER_OVERFLOW — remove overflow guards, use unsafe arithmetic
"""

import ast
import copy
import random
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class BugType(Enum):
    OFF_BY_ONE = "off_by_one"
    BOUNDARY_ERROR = "boundary_error"
    WRONG_OPERATOR = "wrong_operator"
    NONE_DEREF = "none_deref"
    INTEGER_OVERFLOW = "integer_overflow"
    WRONG_VARIABLE = "wrong_variable"
    MISSING_RETURN = "missing_return"
    WRONG_INIT = "wrong_init"
    SWAP_ARGS = "swap_args"
    SWAP_AND_OR = "swap_and_or"
    REMOVE_RETURN = "remove_return"
    FLIP_BOOLEAN = "flip_boolean"
    SWAP_PLUS_MINUS = "swap_plus_minus"
    REMOVE_BASE_CASE = "remove_base_case"
    WRONG_INIT_VALUE = "wrong_init_value"


@dataclass
class MutationResult:
    original_code: str
    mutated_code: str
    bug_type: BugType
    bug_line: int  # 1-indexed line number in the mutated code
    bug_node_ids: list[int] = field(default_factory=list)  # AST node indices affected
    description: str = ""
    function_name: str = ""


# ---------------------------------------------------------------------------
# AST-level mutators
# ---------------------------------------------------------------------------

class OffByOneMutator(ast.NodeTransformer):
    """Mutate numeric constants by ±1 in strategic locations."""

    def __init__(self):
        self.mutations = []
        self.mutated = False

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if self.mutated:
            return node
        # Target: `mid + 1` → `mid + 2`, `n - 1` → `n`, etc.
        if isinstance(node.op, (ast.Add, ast.Sub)):
            if isinstance(node.right, ast.Constant) and isinstance(node.right.value, int):
                original = node.right.value
                if random.random() < 0.5:
                    node.right.value = original + 1
                else:
                    node.right.value = original - 1
                self.mutations.append((node.lineno, f"Changed constant {original} to {node.right.value}"))
                self.mutated = True
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        if self.mutated:
            return node
        # Target: range(start, end) → range(start, end ± 1)
        if isinstance(node.func, ast.Name) and node.func.id == 'range':
            if len(node.args) >= 2:
                end_arg = node.args[-1]
                if isinstance(end_arg, ast.BinOp) and isinstance(end_arg.right, ast.Constant):
                    original = end_arg.right.value
                    end_arg.right.value = original + (1 if random.random() < 0.5 else -1)
                    self.mutations.append((node.lineno, f"Off-by-one in range bound"))
                    self.mutated = True
                elif isinstance(end_arg, ast.Constant) and isinstance(end_arg.value, int):
                    original = end_arg.value
                    end_arg.value = original + (1 if random.random() < 0.5 else -1)
                    self.mutations.append((node.lineno, f"Off-by-one in range end"))
                    self.mutated = True
        return node


class WrongOperatorMutator(ast.NodeTransformer):
    """Swap comparison or arithmetic operators."""

    COMPARE_SWAPS = {
        ast.Lt: [ast.LtE, ast.Gt],
        ast.LtE: [ast.Lt, ast.GtE],
        ast.Gt: [ast.GtE, ast.Lt],
        ast.GtE: [ast.Gt, ast.LtE],
        ast.Eq: [ast.NotEq],
        ast.NotEq: [ast.Eq],
    }

    ARITH_SWAPS = {
        ast.Add: [ast.Sub],
        ast.Sub: [ast.Add],
        ast.Mult: [ast.FloorDiv, ast.Add],
        ast.FloorDiv: [ast.Mult],
        ast.Mod: [ast.FloorDiv],
    }

    def __init__(self):
        self.mutations = []
        self.mutated = False

    def visit_Compare(self, node):
        self.generic_visit(node)
        if self.mutated:
            return node
        for i, op in enumerate(node.ops):
            op_type = type(op)
            if op_type in self.COMPARE_SWAPS:
                new_op_type = random.choice(self.COMPARE_SWAPS[op_type])
                node.ops[i] = new_op_type()
                self.mutations.append((node.lineno, f"Swapped {op_type.__name__} to {new_op_type.__name__}"))
                self.mutated = True
                break
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if self.mutated:
            return node
        op_type = type(node.op)
        if op_type in self.ARITH_SWAPS:
            new_op_type = random.choice(self.ARITH_SWAPS[op_type])
            node.op = new_op_type()
            self.mutations.append((node.lineno, f"Swapped {op_type.__name__} to {new_op_type.__name__}"))
            self.mutated = True
        return node


class BoundaryErrorMutator(ast.NodeTransformer):
    """Remove or corrupt boundary checks (len checks, range guards)."""

    def __init__(self):
        self.mutations = []
        self.mutated = False

    @staticmethod
    def _is_boundary_check(node):
        """Detect boundary checks by walking the AST test expression."""
        dump = ast.dump(node)
        # ast.dump produces patterns like:
        #   Name(id='len')  for len calls
        #   Constant(value=0) for zero comparisons
        patterns = [
            "id='len'",        # len() calls
            "Constant(value=0)",  # == 0, < 0, etc.
            "Constant(value=-1)", # common boundary
        ]
        # Also detect comparisons involving len
        has_len = "id='len'" in dump
        has_compare = isinstance(node, ast.Compare)
        has_bool_with_len = isinstance(node, ast.BoolOp) and "id='len'" in dump
        return any(p in dump for p in patterns) or (has_len and has_compare) or has_bool_with_len

    def visit_If(self, node):
        self.generic_visit(node)
        if self.mutated:
            return node
        if self._is_boundary_check(node.test):
            # Strategy 1: Remove the entire if block (skip the guard)
            if node.orelse:
                self.mutations.append((node.lineno, "Removed boundary check"))
                self.mutated = True
                return node.orelse if isinstance(node.orelse, list) else [node.orelse]
            else:
                # Strategy 2: Negate the condition
                node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
                ast.fix_missing_locations(node)
                self.mutations.append((node.lineno, "Negated boundary check"))
                self.mutated = True
        return node


class NoneDerefMutator(ast.NodeTransformer):
    """Remove None checks, exposing potential None dereference."""

    def __init__(self):
        self.mutations = []
        self.mutated = False

    def visit_If(self, node):
        self.generic_visit(node)
        if self.mutated:
            return node
        test_src = ast.dump(node.test)
        is_none_check = 'None' in test_src or 'is None' in test_src or 'is not None' in test_src
        if is_none_check:
            # Remove the None guard — just execute the body without checking
            if node.orelse:
                self.mutations.append((node.lineno, "Removed None check"))
                self.mutated = True
                return node.orelse if isinstance(node.orelse, list) else [node.orelse]
            else:
                self.mutations.append((node.lineno, "Removed None guard"))
                self.mutated = True
                return ast.Pass()
        return node


class IntegerOverflowMutator(ast.NodeTransformer):
    """Introduce potential integer overflow by replacing safe operations."""

    def __init__(self):
        self.mutations = []
        self.mutated = False

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if self.mutated:
            return node
        # Target: `(low + high) // 2` → `(low + high) // 2` is safe in Python,
        # but we can introduce issues by changing to multiplication or removing division
        if isinstance(node.op, ast.FloorDiv):
            # Remove the floor div — just return the numerator (overflow-style)
            self.mutations.append((node.lineno, "Removed floor division (overflow risk)"))
            self.mutated = True
            return node.left
        if isinstance(node.op, ast.Mod):
            # Remove modulo — allows unbounded values
            self.mutations.append((node.lineno, "Removed modulo operation"))
            self.mutated = True
            return node.left
        return node


class WrongVariableMutator(ast.NodeTransformer):
    """Swap a variable in a comparison, subscript, or arithmetic for another in-scope variable."""

    def __init__(self):
        self.mutations = []
        self.mutated = False
        self.variables = set()
        self._in_target = False

    def _collect_variables(self, tree):
        """Collect variable names assigned in the function (not builtins)."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(getattr(node, 'ctx', None), ast.Store):
                self.variables.add(node.id)
            elif isinstance(node, ast.For) and isinstance(node.target, ast.Name):
                self.variables.add(node.target.id)

    def visit_Compare(self, node):
        """Only swap variables inside comparisons — these reliably cause bugs."""
        self.generic_visit(node)
        return node

    def visit_Subscript(self, node):
        """Swap index variable in array subscripts."""
        if self.mutated:
            return node
        if isinstance(node.slice, ast.Name):
            candidates = [v for v in self.variables if v != node.slice.id]
            if candidates:
                old = node.slice.id
                node.slice.id = random.choice(candidates)
                self.mutations.append((getattr(node, 'lineno', 1),
                                       f"Swapped index '{old}' for '{node.slice.id}'"))
                self.mutated = True
        self.generic_visit(node)
        return node

    def visit_Name(self, node):
        if self.mutated:
            return node
        if not isinstance(getattr(node, 'ctx', None), ast.Load):
            return node
        # Only swap inside comparisons/arithmetic (checked by parent visitor)
        candidates = [v for v in self.variables if v != node.id]
        if candidates and random.random() < 0.15:
            old_name = node.id
            node.id = random.choice(candidates)
            self.mutations.append((getattr(node, 'lineno', 1),
                                   f"Swapped variable '{old_name}' for '{node.id}'"))
            self.mutated = True
        return node


class MissingReturnMutator(ast.NodeTransformer):
    """Remove or corrupt a return statement."""

    def __init__(self):
        self.mutations = []
        self.mutated = False
        self.return_count = 0

    def _count_returns(self, tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.Return):
                self.return_count += 1

    def visit_Return(self, node):
        if self.mutated:
            return node
        # Strategy 1: Remove return value (return x → return None)
        if node.value is not None and random.random() < 0.5:
            self.mutations.append((getattr(node, 'lineno', 1), "Removed return value"))
            node.value = ast.Constant(value=None)
            self.mutated = True
        # Strategy 2: Replace with pass (only if there are other returns)
        elif self.return_count > 1:
            self.mutations.append((getattr(node, 'lineno', 1), "Removed return statement"))
            self.mutated = True
            return ast.Pass()
        return node


class WrongInitMutator(ast.NodeTransformer):
    """Change variable initialization to a wrong value."""

    INIT_SWAPS = {
        0: [1, -1],
        1: [0, 2],
        -1: [0, 1],
        True: [False],
        False: [True],
    }

    def __init__(self):
        self.mutations = []
        self.mutated = False

    def visit_Assign(self, node):
        self.generic_visit(node)
        if self.mutated:
            return node
        if len(node.targets) == 1 and isinstance(node.value, ast.Constant):
            val = node.value.value
            if val in self.INIT_SWAPS:
                new_val = random.choice(self.INIT_SWAPS[val])
                self.mutations.append((getattr(node, 'lineno', 1),
                                       f"Changed init from {val} to {new_val}"))
                node.value = ast.Constant(value=new_val)
                self.mutated = True
            elif isinstance(val, (int, float)) and val != 0:
                # Negate or zero out
                new_val = 0 if random.random() < 0.5 else -val
                self.mutations.append((getattr(node, 'lineno', 1),
                                       f"Changed init from {val} to {new_val}"))
                node.value = ast.Constant(value=new_val)
                self.mutated = True
        # Swap empty list init with None or vice versa
        elif (len(node.targets) == 1 and isinstance(node.value, ast.List)
              and len(node.value.elts) == 0):
            self.mutations.append((getattr(node, 'lineno', 1),
                                   "Changed [] init to None"))
            node.value = ast.Constant(value=None)
            self.mutated = True
        return node


class SwapArgsMutator(ast.NodeTransformer):
    """Swap arguments in function calls."""

    def __init__(self):
        self.mutations = []
        self.mutated = False

    def visit_Call(self, node):
        self.generic_visit(node)
        if self.mutated:
            return node
        # Skip builtins that take single args
        if isinstance(node.func, ast.Name) and node.func.id in ('len', 'print', 'str', 'int',
                                                                   'float', 'bool', 'type',
                                                                   'abs', 'set', 'list', 'dict',
                                                                   'sorted', 'reversed', 'enumerate'):
            return node
        if len(node.args) >= 2 and random.random() < 0.4:
            # Swap first two args
            i, j = 0, 1
            if len(node.args) > 2:
                i, j = random.sample(range(len(node.args)), 2)
            node.args[i], node.args[j] = node.args[j], node.args[i]
            self.mutations.append((getattr(node, 'lineno', 1), "Swapped function arguments"))
            self.mutated = True
        return node


# ---------------------------------------------------------------------------
# New mutator classes for expanded bug coverage
# ---------------------------------------------------------------------------

class SwapAndOrMutator(ast.NodeTransformer):
    """Swap `and` with `or` and vice versa in boolean expressions."""

    def __init__(self):
        self.mutations = []
        self.mutated = False

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        if self.mutated:
            return node
        if isinstance(node.op, ast.And):
            node.op = ast.Or()
            self.mutations.append((getattr(node, 'lineno', 1), "Swapped 'and' to 'or'"))
            self.mutated = True
        elif isinstance(node.op, ast.Or):
            node.op = ast.And()
            self.mutations.append((getattr(node, 'lineno', 1), "Swapped 'or' to 'and'"))
            self.mutated = True
        return node


class RemoveReturnMutator(ast.NodeTransformer):
    """Delete a return statement from a branch entirely (replace with pass)."""

    def __init__(self):
        self.mutations = []
        self.mutated = False
        self.return_count = 0

    def _count_returns(self, tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.Return):
                self.return_count += 1

    def visit_Return(self, node):
        if self.mutated:
            return node
        # Only remove if there are multiple returns (keep function somewhat valid)
        if self.return_count > 1 and random.random() < 0.6:
            self.mutations.append((getattr(node, 'lineno', 1),
                                   "Deleted return statement from branch"))
            self.mutated = True
            return ast.Pass()
        return node


class FlipBooleanMutator(ast.NodeTransformer):
    """Swap True with False and vice versa."""

    def __init__(self):
        self.mutations = []
        self.mutated = False

    def visit_Constant(self, node):
        if self.mutated:
            return node
        if node.value is True:
            node.value = False
            self.mutations.append((getattr(node, 'lineno', 1), "Flipped True to False"))
            self.mutated = True
        elif node.value is False:
            node.value = True
            self.mutations.append((getattr(node, 'lineno', 1), "Flipped False to True"))
            self.mutated = True
        return node


class SwapPlusMinusMutator(ast.NodeTransformer):
    """Swap + with - and vice versa."""

    def __init__(self):
        self.mutations = []
        self.mutated = False

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if self.mutated:
            return node
        if isinstance(node.op, ast.Add):
            node.op = ast.Sub()
            self.mutations.append((getattr(node, 'lineno', 1), "Swapped '+' to '-'"))
            self.mutated = True
        elif isinstance(node.op, ast.Sub):
            node.op = ast.Add()
            self.mutations.append((getattr(node, 'lineno', 1), "Swapped '-' to '+'"))
            self.mutated = True
        return node

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        if self.mutated:
            return node
        if isinstance(node.op, ast.Add):
            node.op = ast.Sub()
            self.mutations.append((getattr(node, 'lineno', 1), "Swapped '+=' to '-='"))
            self.mutated = True
        elif isinstance(node.op, ast.Sub):
            node.op = ast.Add()
            self.mutations.append((getattr(node, 'lineno', 1), "Swapped '-=' to '+='"))
            self.mutated = True
        return node


class RemoveBaseCaseMutator(ast.NodeTransformer):
    """Remove the base case from a recursive function."""

    def __init__(self):
        self.mutations = []
        self.mutated = False
        self.has_recursion = False
        self.func_name = None

    def _detect_recursion(self, tree):
        """Check if function calls itself."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self.func_name = node.name
        if self.func_name is None:
            return
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == self.func_name:
                    self.has_recursion = True

    def visit_If(self, node):
        self.generic_visit(node)
        if self.mutated or not self.has_recursion:
            return node
        # Base cases typically return a constant or simple value early
        if isinstance(node.body, list) and len(node.body) == 1:
            stmt = node.body[0]
            if isinstance(stmt, ast.Return):
                # This looks like a base case — remove the entire if block
                self.mutations.append((getattr(node, 'lineno', 1),
                                       "Removed base case from recursive function"))
                self.mutated = True
                if node.orelse:
                    return node.orelse if isinstance(node.orelse, list) else [node.orelse]
                return ast.Pass()
        return node


class WrongInitValueMutator(ast.NodeTransformer):
    """Initialize variables to semantically wrong values (0→1, empty→None, etc.)."""

    def __init__(self):
        self.mutations = []
        self.mutated = False

    def visit_Assign(self, node):
        self.generic_visit(node)
        if self.mutated:
            return node
        if len(node.targets) != 1:
            return node
        # Swap numeric inits
        if isinstance(node.value, ast.Constant):
            val = node.value.value
            new_val = None
            if val == 0:
                new_val = 1
            elif val == 1:
                new_val = 0
            elif val == -1:
                new_val = 0
            elif val is None:
                # None → empty list
                node.value = ast.List(elts=[], ctx=ast.Load())
                ast.fix_missing_locations(node)
                self.mutations.append((getattr(node, 'lineno', 1),
                                       "Changed None init to []"))
                self.mutated = True
                return node
            if new_val is not None:
                self.mutations.append((getattr(node, 'lineno', 1),
                                       f"Changed init from {val} to {new_val}"))
                node.value = ast.Constant(value=new_val)
                self.mutated = True
        # Swap empty list → None
        elif isinstance(node.value, ast.List) and len(node.value.elts) == 0:
            self.mutations.append((getattr(node, 'lineno', 1),
                                   "Changed [] init to None"))
            node.value = ast.Constant(value=None)
            self.mutated = True
        # Swap empty dict → None
        elif isinstance(node.value, ast.Dict) and len(node.value.keys) == 0:
            self.mutations.append((getattr(node, 'lineno', 1),
                                   "Changed {} init to None"))
            node.value = ast.Constant(value=None)
            self.mutated = True
        return node


# ---------------------------------------------------------------------------
# Main mutation interface
# ---------------------------------------------------------------------------

MUTATORS = {
    BugType.OFF_BY_ONE: OffByOneMutator,
    BugType.WRONG_OPERATOR: WrongOperatorMutator,
    BugType.BOUNDARY_ERROR: BoundaryErrorMutator,
    BugType.NONE_DEREF: NoneDerefMutator,
    BugType.INTEGER_OVERFLOW: IntegerOverflowMutator,
    BugType.WRONG_VARIABLE: WrongVariableMutator,
    BugType.MISSING_RETURN: MissingReturnMutator,
    BugType.WRONG_INIT: WrongInitMutator,
    BugType.SWAP_ARGS: SwapArgsMutator,
    BugType.SWAP_AND_OR: SwapAndOrMutator,
    BugType.REMOVE_RETURN: RemoveReturnMutator,
    BugType.FLIP_BOOLEAN: FlipBooleanMutator,
    BugType.SWAP_PLUS_MINUS: SwapPlusMinusMutator,
    BugType.REMOVE_BASE_CASE: RemoveBaseCaseMutator,
    BugType.WRONG_INIT_VALUE: WrongInitValueMutator,
}


def mutate_function(code: str, bug_type: BugType, function_name: str = "") -> Optional[MutationResult]:
    """
    Apply a single mutation of the given bug_type to the code.
    Returns MutationResult or None if mutation couldn't be applied.
    """
    code = textwrap.dedent(code).strip()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    mutator_cls = MUTATORS[bug_type]
    mutator = mutator_cls()

    # Special setup for mutators that need pre-analysis
    if isinstance(mutator, WrongVariableMutator):
        mutator._collect_variables(tree)
    if isinstance(mutator, MissingReturnMutator):
        mutator._count_returns(tree)
    if isinstance(mutator, RemoveReturnMutator):
        mutator._count_returns(tree)
    if isinstance(mutator, RemoveBaseCaseMutator):
        mutator._detect_recursion(tree)

    mutated_tree = mutator.visit(copy.deepcopy(tree))

    if not mutator.mutated or len(mutator.mutations) == 0:
        return None

    # Fix missing line numbers
    ast.fix_missing_locations(mutated_tree)

    try:
        mutated_code = ast.unparse(mutated_tree)
    except Exception:
        return None

    # Verify the mutation actually changed something
    if mutated_code == ast.unparse(tree):
        return None

    bug_line = mutator.mutations[0][0]
    description = mutator.mutations[0][1]

    return MutationResult(
        original_code=code,
        mutated_code=mutated_code,
        bug_type=bug_type,
        bug_line=bug_line,
        description=description,
        function_name=function_name,
    )


    # Bug types that produce clean, unambiguous mutations
RELIABLE_BUG_TYPES = [
    BugType.OFF_BY_ONE,
    BugType.BOUNDARY_ERROR,
    BugType.WRONG_OPERATOR,
    BugType.NONE_DEREF,
    BugType.INTEGER_OVERFLOW,
    BugType.MISSING_RETURN,
    BugType.WRONG_INIT,
    BugType.SWAP_AND_OR,
    BugType.REMOVE_RETURN,
    BugType.FLIP_BOOLEAN,
    BugType.SWAP_PLUS_MINUS,
    BugType.REMOVE_BASE_CASE,
    BugType.WRONG_INIT_VALUE,
]


def generate_all_mutations(code: str, function_name: str = "") -> list[MutationResult]:
    """Generate all possible mutation types for a given function."""
    results = []
    for bug_type in RELIABLE_BUG_TYPES:
        for _ in range(3):  # Try multiple times due to randomness
            result = mutate_function(code, bug_type, function_name)
            if result is not None:
                results.append(result)
                break
    return results
