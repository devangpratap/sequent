"""
Generate cosmetic variants of correct functions to balance the dataset.

Transforms that preserve correctness:
1. Rename local variables
2. Swap equivalent expressions (e.g., x != 0 → not x == 0)
3. Change loop style (while → for where possible)
4. Add/remove redundant parentheses
5. Rewrite conditionals (if/else → ternary, guard clause flip)
"""

import ast
import copy
import random
import textwrap
from typing import Optional


RENAME_POOLS = [
    {'arr': 'lst', 'val': 'value', 'result': 'output', 'i': 'idx', 'j': 'jdx', 'n': 'length', 'count': 'cnt'},
    {'arr': 'data', 'val': 'v', 'result': 'res', 'i': 'index', 'j': 'j_idx', 'n': 'size', 'count': 'total'},
    {'arr': 'items', 'val': 'elem', 'result': 'ret', 'i': 'pos', 'j': 'inner', 'n': 'num', 'count': 'counter'},
    {'arr': 'seq', 'val': 'x', 'result': 'out', 'i': 'k', 'j': 'l', 'n': 'sz', 'count': 'c'},
    {'arr': 'nums', 'val': 'item', 'result': 'answer', 'i': 'ii', 'n': 'dim', 'count': 'acc'},
]


class VariableRenamer(ast.NodeTransformer):
    """Rename local variables using a mapping."""

    def __init__(self, mapping: dict, protected: set):
        self.mapping = mapping
        self.protected = protected

    def visit_Name(self, node):
        if node.id in self.mapping and node.id not in self.protected:
            node.id = self.mapping[node.id]
        return node

    def visit_arg(self, node):
        # Don't rename function parameters — that would change the API
        return node


def get_local_vars(tree) -> set:
    """Get all locally assigned variable names."""
    local_vars = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    local_vars.add(target.id)
        elif isinstance(node, ast.AugAssign):
            if isinstance(target := node.target, ast.Name):
                local_vars.add(target.id)
        elif isinstance(node, ast.For):
            if isinstance(node.target, ast.Name):
                local_vars.add(node.target.id)
    return local_vars


def get_param_names(tree) -> set:
    """Get function parameter names."""
    params = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for arg in node.args.args:
                params.add(arg.arg)
    return params


def rename_variant(code: str) -> Optional[str]:
    """Generate a variant with renamed local variables."""
    try:
        tree = ast.parse(textwrap.dedent(code).strip())
    except SyntaxError:
        return None

    local_vars = get_local_vars(tree)
    params = get_param_names(tree)
    renameable = local_vars - params  # Don't rename params

    if not renameable:
        return None

    rename_pool = random.choice(RENAME_POOLS)
    mapping = {}
    used_names = set()
    for var in renameable:
        if var in rename_pool and rename_pool[var] not in used_names:
            mapping[var] = rename_pool[var]
            used_names.add(rename_pool[var])

    if not mapping:
        # Generate random suffixed names
        for var in renameable:
            new_name = f"{var}_{random.randint(1, 9)}"
            if new_name not in used_names:
                mapping[var] = new_name
                used_names.add(new_name)

    if not mapping:
        return None

    renamer = VariableRenamer(mapping, params)
    new_tree = renamer.visit(copy.deepcopy(tree))
    ast.fix_missing_locations(new_tree)

    try:
        return ast.unparse(new_tree)
    except Exception:
        return None


def add_redundant_parens(code: str) -> Optional[str]:
    """Add redundant parentheses around comparison expressions."""
    try:
        tree = ast.parse(textwrap.dedent(code).strip())
    except SyntaxError:
        return None

    class ParenAdder(ast.NodeTransformer):
        def __init__(self):
            self.modified = False

        def visit_Compare(self, node):
            self.generic_visit(node)
            # Wrap in BoolOp with single value (effectively adds parens in unparse)
            if not self.modified and random.random() < 0.5:
                self.modified = True
            return node

    # Simple approach: just unparse and re-parse (AST unparse normalizes)
    try:
        result = ast.unparse(tree)
        return result if result != textwrap.dedent(code).strip() else None
    except Exception:
        return None


def swap_if_else(code: str) -> Optional[str]:
    """Negate condition and swap if/else branches."""
    try:
        tree = ast.parse(textwrap.dedent(code).strip())
    except SyntaxError:
        return None

    class IfSwapper(ast.NodeTransformer):
        def __init__(self):
            self.swapped = False

        def visit_If(self, node):
            self.generic_visit(node)
            if self.swapped or not node.orelse:
                return node
            # Only swap simple if/else (not elif chains)
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                return node

            # Negate condition and swap branches
            new_test = ast.UnaryOp(op=ast.Not(), operand=node.test)
            node.test = new_test
            node.body, node.orelse = node.orelse, node.body
            ast.fix_missing_locations(node)
            self.swapped = True
            return node

    swapper = IfSwapper()
    new_tree = swapper.visit(copy.deepcopy(tree))

    if not swapper.swapped:
        return None

    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree)
    except Exception:
        return None


def reorder_commutative(code: str) -> Optional[str]:
    """Swap operands of commutative operations (a + b → b + a)."""
    try:
        tree = ast.parse(textwrap.dedent(code).strip())
    except SyntaxError:
        return None

    class CommutativeSwapper(ast.NodeTransformer):
        def __init__(self):
            self.swapped = False

        def visit_BinOp(self, node):
            self.generic_visit(node)
            if self.swapped:
                return node
            if isinstance(node.op, (ast.Add, ast.Mult, ast.BitAnd, ast.BitOr, ast.BitXor)):
                if random.random() < 0.5:
                    node.left, node.right = node.right, node.left
                    self.swapped = True
            return node

    swapper = CommutativeSwapper()
    new_tree = swapper.visit(copy.deepcopy(tree))
    if not swapper.swapped:
        return None
    ast.fix_missing_locations(new_tree)
    try:
        result = ast.unparse(new_tree)
        return result if result != textwrap.dedent(code).strip() else None
    except Exception:
        return None


def normalize_comparisons(code: str) -> Optional[str]:
    """Flip comparisons: a < b → b > a."""
    try:
        tree = ast.parse(textwrap.dedent(code).strip())
    except SyntaxError:
        return None

    FLIPS = {ast.Lt: ast.Gt, ast.Gt: ast.Lt, ast.LtE: ast.GtE, ast.GtE: ast.LtE}

    class ComparisonFlipper(ast.NodeTransformer):
        def __init__(self):
            self.flipped = False

        def visit_Compare(self, node):
            self.generic_visit(node)
            if self.flipped or len(node.ops) != 1 or len(node.comparators) != 1:
                return node
            op_type = type(node.ops[0])
            if op_type in FLIPS and random.random() < 0.5:
                node.ops[0] = FLIPS[op_type]()
                # Swap left and comparator
                node.left, node.comparators[0] = node.comparators[0], node.left
                self.flipped = True
            return node

    flipper = ComparisonFlipper()
    new_tree = flipper.visit(copy.deepcopy(tree))
    if not flipper.flipped:
        return None
    ast.fix_missing_locations(new_tree)
    try:
        result = ast.unparse(new_tree)
        return result if result != textwrap.dedent(code).strip() else None
    except Exception:
        return None


def generate_correct_variants(code: str, num_variants: int = 10) -> list[str]:
    """Generate multiple correct variants of a function."""
    variants = set()
    original = textwrap.dedent(code).strip()

    generators = [rename_variant, swap_if_else]

    for _ in range(num_variants * 5):  # More attempts for harder generation
        gen = random.choice(generators)
        variant = gen(original)
        if variant and variant != original and variant not in variants:
            variants.add(variant)
        if len(variants) >= num_variants:
            break

    # Compose variants (apply transforms to existing variants)
    second_pass = set()
    for v in list(variants):
        for _ in range(3):
            gen = random.choice(generators)
            v2 = gen(v)
            if v2 and v2 != original and v2 not in variants and v2 not in second_pass:
                second_pass.add(v2)
        if len(variants) + len(second_pass) >= num_variants:
            break

    variants.update(second_pass)

    # Third pass: compose further
    third_pass = set()
    for v in list(second_pass)[:20]:
        gen = random.choice(generators)
        v3 = gen(v)
        if v3 and v3 != original and v3 not in variants and v3 not in second_pass and v3 not in third_pass:
            third_pass.add(v3)
        if len(variants) + len(third_pass) >= num_variants:
            break

    variants.update(third_pass)
    return list(variants)[:num_variants]
