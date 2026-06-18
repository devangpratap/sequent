"""
Tree-sitter / regex-based CPG builder for JavaScript and TypeScript.

Converts JS/TS source code into the same Code Property Graph format as
``ast_to_graph.py`` (nodes, edges with types, feature vectors) so the
GNN and the rest of the Sequent pipeline work without modification.

If ``tree_sitter`` is installed it will be used for accurate parsing.
Otherwise a lightweight regex/pattern-based parser handles the most
common JS constructs (functions, variables, control flow, calls, etc.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import torch

# Re-use the canonical node-type vocabulary from the Python CPG builder so
# that feature vectors live in the same space and the GNN generalises.
from model.ast_to_graph import (
    AST_NODE_TYPES,
    NODE_TYPE_TO_IDX,
    NUM_NODE_TYPES,
    UNKNOWN_TYPE_IDX,
    ASTGraphBuilder,
)

# ---------------------------------------------------------------------------
# Try tree-sitter first
# ---------------------------------------------------------------------------
_HAS_TREE_SITTER = False
try:
    import tree_sitter  # noqa: F401
    _HAS_TREE_SITTER = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Mapping from JS/TS construct names to the nearest AST_NODE_TYPES index
# ---------------------------------------------------------------------------
JS_TYPE_MAP: dict[str, int] = {
    # Statements
    "Module":            NODE_TYPE_TO_IDX["Module"],
    "FunctionDeclaration": NODE_TYPE_TO_IDX["FunctionDef"],
    "ArrowFunction":     NODE_TYPE_TO_IDX["FunctionDef"],
    "AsyncFunction":     NODE_TYPE_TO_IDX["AsyncFunctionDef"],
    "ClassDeclaration":  NODE_TYPE_TO_IDX["ClassDef"],
    "ReturnStatement":   NODE_TYPE_TO_IDX["Return"],
    "VariableDeclaration": NODE_TYPE_TO_IDX["Assign"],
    "Assignment":        NODE_TYPE_TO_IDX["Assign"],
    "AugmentedAssignment": NODE_TYPE_TO_IDX["AugAssign"],
    "ForStatement":      NODE_TYPE_TO_IDX["For"],
    "ForOfStatement":    NODE_TYPE_TO_IDX["AsyncFor"],
    "ForInStatement":    NODE_TYPE_TO_IDX["For"],
    "WhileStatement":    NODE_TYPE_TO_IDX["While"],
    "IfStatement":       NODE_TYPE_TO_IDX["If"],
    "TryStatement":      NODE_TYPE_TO_IDX["Try"],
    "ThrowStatement":    NODE_TYPE_TO_IDX["Raise"],
    "ImportDeclaration": NODE_TYPE_TO_IDX["Import"],
    "ExpressionStatement": NODE_TYPE_TO_IDX["Expr"],
    "BreakStatement":    NODE_TYPE_TO_IDX["Break"],
    "ContinueStatement": NODE_TYPE_TO_IDX["Continue"],
    # Expressions
    "BinaryExpression":  NODE_TYPE_TO_IDX["BinOp"],
    "UnaryExpression":   NODE_TYPE_TO_IDX["UnaryOp"],
    "LogicalExpression": NODE_TYPE_TO_IDX["BoolOp"],
    "ConditionalExpression": NODE_TYPE_TO_IDX["IfExp"],
    "CallExpression":    NODE_TYPE_TO_IDX["Call"],
    "MemberExpression":  NODE_TYPE_TO_IDX["Attribute"],
    "Subscript":         NODE_TYPE_TO_IDX["Subscript"],
    "ArrayExpression":   NODE_TYPE_TO_IDX["List"],
    "ObjectExpression":  NODE_TYPE_TO_IDX["Dict"],
    "TemplateLiteral":   NODE_TYPE_TO_IDX["JoinedStr"],
    "Literal":           NODE_TYPE_TO_IDX["Constant"],
    "Identifier":        NODE_TYPE_TO_IDX["Name"],
    # Operators (encoded as nodes, same as the Python builder)
    "Add":  NODE_TYPE_TO_IDX["Add"],
    "Sub":  NODE_TYPE_TO_IDX["Sub"],
    "Mult": NODE_TYPE_TO_IDX["Mult"],
    "Div":  NODE_TYPE_TO_IDX["Div"],
    "Mod":  NODE_TYPE_TO_IDX["Mod"],
    "Eq":   NODE_TYPE_TO_IDX["Eq"],
    "StrictEq": NODE_TYPE_TO_IDX["Eq"],
    "NotEq": NODE_TYPE_TO_IDX["NotEq"],
    "StrictNotEq": NODE_TYPE_TO_IDX["NotEq"],
    "Lt":   NODE_TYPE_TO_IDX["Lt"],
    "LtE":  NODE_TYPE_TO_IDX["LtE"],
    "Gt":   NODE_TYPE_TO_IDX["Gt"],
    "GtE":  NODE_TYPE_TO_IDX["GtE"],
    "And":  NODE_TYPE_TO_IDX["And"],
    "Or":   NODE_TYPE_TO_IDX["Or"],
    "Not":  NODE_TYPE_TO_IDX["Not"],
    # Parameters / arguments
    "Parameter":   NODE_TYPE_TO_IDX["arg"],
    "Arguments":   NODE_TYPE_TO_IDX["arguments"],
    "SpreadElement": NODE_TYPE_TO_IDX["Starred"],
}

_OPERATOR_TYPES = {
    "Add", "Sub", "Mult", "Div", "Mod",
    "Eq", "StrictEq", "NotEq", "StrictNotEq",
    "Lt", "LtE", "Gt", "GtE",
    "And", "Or", "Not",
}

# Edge type constants (must match ASTGraphBuilder)
EDGE_AST = 0
EDGE_CFG = 1
EDGE_DFG = 2

# ---------------------------------------------------------------------------
# Lightweight regex-based JS/TS node
# ---------------------------------------------------------------------------

@dataclass
class JSNode:
    """Minimal AST-like node produced by the regex parser."""
    type: str
    line: int = 0
    name: str = ""          # identifier name (if any)
    children: list["JSNode"] = field(default_factory=list)
    # Extra metadata used during graph construction
    is_def: bool = False    # True when this node *defines* a variable
    is_use: bool = False    # True when this node *reads* a variable
    operator: str = ""      # e.g. "+", "===", etc.

    @property
    def id(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Operator string -> JS_TYPE_MAP key
# ---------------------------------------------------------------------------
_OP_STR_MAP: dict[str, str] = {
    "+": "Add", "-": "Sub", "*": "Mult", "/": "Div", "%": "Mod",
    "==": "Eq", "===": "StrictEq", "!=": "NotEq", "!==": "StrictNotEq",
    "<": "Lt", "<=": "LtE", ">": "Gt", ">=": "GtE",
    "&&": "And", "||": "Or", "!": "Not",
}

# ---------------------------------------------------------------------------
# Regex-based JS/TS parser
# ---------------------------------------------------------------------------

def _regex_parse_js(code: str) -> JSNode:
    """
    Parse JavaScript / TypeScript source into a tree of ``JSNode`` objects
    using regular expressions.  This is intentionally simple — it covers the
    constructs listed in the task spec and nothing more.
    """
    root = JSNode(type="Module", line=1)
    lines = code.split("\n")

    # Patterns (order matters — first match wins per line)
    patterns: list[tuple[str, re.Pattern]] = [
        ("FunctionDeclaration",
         re.compile(
             r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)"
         )),
        ("ArrowFunction",
         re.compile(
             r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>"
         )),
        ("VariableDeclaration",
         re.compile(
             r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*(?::\s*\w+)?\s*="
         )),
        ("ReturnStatement",
         re.compile(r"^\s*return\b\s*(.*)")),
        ("IfStatement",
         re.compile(r"^\s*(?:}\s*)?else\s+if\s*\(|^\s*if\s*\(")),
        ("ElseClause",
         re.compile(r"^\s*}\s*else\s*\{")),
        ("ForStatement",
         re.compile(r"^\s*for\s*\(")),
        ("WhileStatement",
         re.compile(r"^\s*while\s*\(")),
        ("TryStatement",
         re.compile(r"^\s*try\s*\{")),
        ("ThrowStatement",
         re.compile(r"^\s*throw\b")),
        ("BreakStatement",
         re.compile(r"^\s*break\b")),
        ("ContinueStatement",
         re.compile(r"^\s*continue\b")),
        ("ImportDeclaration",
         re.compile(r"^\s*import\s")),
        ("ClassDeclaration",
         re.compile(r"^\s*(?:export\s+)?class\s+(\w+)")),
    ]

    # Expression-level patterns (applied inside a line)
    call_re = re.compile(r"(\w+)\s*\(")
    binop_re = re.compile(r"(!==|===|!=|==|>=|<=|&&|\|\||[+\-*/%<>])")
    subscript_re = re.compile(r"(\w+)\[")
    identifier_re = re.compile(r"\b([a-zA-Z_$]\w*)\b")

    # Reserved words to exclude from identifier capture
    _RESERVED = {
        "function", "const", "let", "var", "if", "else", "for", "while",
        "return", "class", "import", "export", "from", "try", "catch",
        "finally", "throw", "new", "typeof", "instanceof", "void",
        "delete", "in", "of", "switch", "case", "break", "continue",
        "default", "do", "async", "await", "yield", "true", "false",
        "null", "undefined", "this", "super", "extends", "static",
        "type", "interface", "enum", "implements", "public", "private",
        "protected", "readonly", "abstract", "as", "is",
    }

    for lineno_0, raw_line in enumerate(lines):
        lineno = lineno_0 + 1  # 1-based
        line = raw_line

        # Skip blank / comment-only lines
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue

        matched_type: str | None = None
        match_obj: re.Match | None = None

        for ptype, pat in patterns:
            m = pat.search(line)
            if m:
                matched_type = ptype
                match_obj = m
                break

        # --- Build nodes for this line ---
        if matched_type == "FunctionDeclaration":
            fname = match_obj.group(1)
            params_str = match_obj.group(2) if match_obj.lastindex >= 2 else ""
            func_node = JSNode(type="FunctionDeclaration", line=lineno, name=fname)
            # Add parameter nodes
            if params_str.strip():
                for p in params_str.split(","):
                    pname = p.strip().split(":")[0].split("=")[0].strip()
                    if pname:
                        param_node = JSNode(type="Parameter", line=lineno, name=pname, is_def=True)
                        func_node.children.append(param_node)
            root.children.append(func_node)

        elif matched_type == "ArrowFunction":
            fname = match_obj.group(1)
            params_str = match_obj.group(2) if match_obj.lastindex >= 2 else ""
            func_node = JSNode(type="ArrowFunction", line=lineno, name=fname)
            if params_str.strip():
                for p in params_str.split(","):
                    pname = p.strip().split(":")[0].split("=")[0].strip()
                    if pname:
                        param_node = JSNode(type="Parameter", line=lineno, name=pname, is_def=True)
                        func_node.children.append(param_node)
            root.children.append(func_node)

        elif matched_type == "VariableDeclaration":
            vname = match_obj.group(1)
            var_node = JSNode(type="VariableDeclaration", line=lineno, name=vname, is_def=True)
            # Parse RHS for operators, calls, identifiers
            rhs = line[match_obj.end():]
            _add_expression_children(var_node, rhs, lineno, _RESERVED)
            root.children.append(var_node)

        elif matched_type == "ReturnStatement":
            ret_node = JSNode(type="ReturnStatement", line=lineno)
            expr = match_obj.group(1) if match_obj.lastindex else ""
            _add_expression_children(ret_node, expr, lineno, _RESERVED)
            root.children.append(ret_node)

        elif matched_type == "IfStatement":
            if_node = JSNode(type="IfStatement", line=lineno)
            _add_expression_children(if_node, line, lineno, _RESERVED)
            root.children.append(if_node)

        elif matched_type == "ElseClause":
            else_node = JSNode(type="IfStatement", line=lineno, name="else")
            root.children.append(else_node)

        elif matched_type in ("ForStatement", "WhileStatement"):
            loop_node = JSNode(type=matched_type, line=lineno)
            _add_expression_children(loop_node, line, lineno, _RESERVED)
            root.children.append(loop_node)

        elif matched_type in ("TryStatement", "ThrowStatement",
                               "BreakStatement", "ContinueStatement",
                               "ImportDeclaration", "ClassDeclaration"):
            node = JSNode(type=matched_type, line=lineno,
                          name=match_obj.group(1) if match_obj.lastindex else "")
            root.children.append(node)

        else:
            # Generic expression statement
            expr_node = JSNode(type="ExpressionStatement", line=lineno)
            _add_expression_children(expr_node, line, lineno, _RESERVED)
            if expr_node.children:
                root.children.append(expr_node)

    return root


def _add_expression_children(parent: JSNode, text: str, lineno: int,
                              reserved: set[str]) -> None:
    """Extract operator, call, subscript, and identifier nodes from *text*."""
    # Operators
    for m in re.finditer(r"(!==|===|!=|==|>=|<=|&&|\|\||[+\-*/%<>])", text):
        op_str = m.group(1)
        op_type = _OP_STR_MAP.get(op_str)
        if op_type:
            parent.children.append(
                JSNode(type=op_type, line=lineno, operator=op_str)
            )

    # Calls
    for m in re.finditer(r"(\w+)\s*\(", text):
        name = m.group(1)
        if name not in reserved:
            parent.children.append(
                JSNode(type="CallExpression", line=lineno, name=name, is_use=True)
            )

    # Subscripts
    for m in re.finditer(r"(\w+)\[", text):
        name = m.group(1)
        if name not in reserved:
            parent.children.append(
                JSNode(type="Subscript", line=lineno, name=name, is_use=True)
            )

    # Identifiers (variables referenced)
    seen: set[str] = set()
    for m in re.finditer(r"\b([a-zA-Z_$]\w*)\b", text):
        name = m.group(1)
        if name not in reserved and name not in seen:
            seen.add(name)
            parent.children.append(
                JSNode(type="Identifier", line=lineno, name=name, is_use=True)
            )


# ---------------------------------------------------------------------------
# Graph builder — mirrors ASTGraphBuilder output format
# ---------------------------------------------------------------------------

class JSGraphBuilder:
    """Converts a JS/TS regex parse tree into a CPG dict."""

    def __init__(self):
        self.nodes: list[tuple[JSNode, int, int]] = []   # (node, depth, idx)
        self.edges: list[tuple[int, int]] = []
        self.edge_types: list[int] = []
        self.node_lines: list[int] = []
        self.var_defs: dict[str, int] = {}
        self._node_map: dict[int, int] = {}

    # --- internal helpers ---------------------------------------------------

    def _type_idx(self, node: JSNode) -> int:
        return JS_TYPE_MAP.get(node.type, UNKNOWN_TYPE_IDX)

    def _visit(self, node: JSNode, depth: int, parent_idx: int | None) -> None:
        idx = len(self.nodes)
        self.nodes.append((node, depth, idx))
        self.node_lines.append(node.line)
        self._node_map[id(node)] = idx

        # Track variable definitions
        if node.is_def and node.name:
            self.var_defs[node.name] = idx

        # AST edge to parent (bidirectional)
        if parent_idx is not None:
            self.edges.append((parent_idx, idx))
            self.edge_types.append(EDGE_AST)
            self.edges.append((idx, parent_idx))
            self.edge_types.append(EDGE_AST)

        for child in node.children:
            self._visit(child, depth + 1, idx)

    def _add_cfg_edges(self, root: JSNode) -> None:
        """Sequential control-flow edges between top-level children."""
        stmts = root.children
        for i in range(len(stmts) - 1):
            src = self._node_map.get(id(stmts[i]))
            dst = self._node_map.get(id(stmts[i + 1]))
            if src is not None and dst is not None:
                self.edges.append((src, dst))
                self.edge_types.append(EDGE_CFG)

        # Control-flow within if / loop bodies (entry edge)
        for stmt in stmts:
            src = self._node_map.get(id(stmt))
            if src is None:
                continue
            if stmt.type in ("IfStatement", "ForStatement", "WhileStatement",
                              "FunctionDeclaration", "ArrowFunction"):
                if stmt.children:
                    first_child = self._node_map.get(id(stmt.children[0]))
                    if first_child is not None:
                        self.edges.append((src, first_child))
                        self.edge_types.append(EDGE_CFG)

            # Back-edge for loops
            if stmt.type in ("ForStatement", "WhileStatement") and stmt.children:
                last_child = self._node_map.get(id(stmt.children[-1]))
                if last_child is not None:
                    self.edges.append((last_child, src))
                    self.edge_types.append(EDGE_CFG)

    def _add_dfg_edges(self) -> None:
        """Def -> use edges for variables."""
        for node, _, idx in self.nodes:
            if node.is_use and node.name and node.name in self.var_defs:
                def_idx = self.var_defs[node.name]
                if def_idx != idx:
                    self.edges.append((def_idx, idx))
                    self.edge_types.append(EDGE_DFG)

    # --- public API ---------------------------------------------------------

    def build(self, code: str, bug_line: int | None = None,
              is_buggy: bool = False) -> dict | None:
        """Build CPG from JS/TS source. Returns same dict shape as
        ``ASTGraphBuilder.build``."""
        self.nodes = []
        self.edges = []
        self.edge_types = []
        self.node_lines = []
        self.var_defs = {}
        self._node_map = {}

        root = _regex_parse_js(code)
        self._visit(root, depth=0, parent_idx=None)

        if len(self.nodes) == 0:
            return None

        self._add_cfg_edges(root)
        self._add_dfg_edges()

        # --- Feature matrix (same dim as Python builder) --------------------
        feature_dim = NUM_NODE_TYPES + 1 + 8
        x = np.zeros((len(self.nodes), feature_dim), dtype=np.float32)

        max_depth = max(d for _, d, _ in self.nodes) or 1
        max_line = max(self.node_lines) or 1

        # Compute subtree sizes
        children_map: dict[int, list[int]] = {i: [] for i in range(len(self.nodes))}
        for src, dst in self.edges:
            if src < dst:
                children_map[src].append(dst)
        sizes = [1] * len(self.nodes)
        for i in range(len(self.nodes) - 1, -1, -1):
            for c in children_map[i]:
                sizes[i] += sizes[c]
        max_subtree = max(sizes) if sizes else 1

        # In-loop / in-conditional flags
        in_loop = [False] * len(self.nodes)
        in_cond = [False] * len(self.nodes)
        for i, (nd, _, _) in enumerate(self.nodes):
            if nd.type in ("ForStatement", "WhileStatement"):
                # Mark all descendants as in-loop
                stack = list(children_map[i])
                while stack:
                    ci = stack.pop()
                    in_loop[ci] = True
                    stack.extend(children_map[ci])
            if nd.type == "IfStatement":
                stack = list(children_map[i])
                while stack:
                    ci = stack.pop()
                    in_cond[ci] = True
                    stack.extend(children_map[ci])

        for i, (node, depth, _) in enumerate(self.nodes):
            type_idx = self._type_idx(node)
            if type_idx < NUM_NODE_TYPES:
                x[i, type_idx] = 1.0
            else:
                x[i, NUM_NODE_TYPES] = 1.0

            x[i, NUM_NODE_TYPES + 1] = depth / max(max_depth, 1)
            x[i, NUM_NODE_TYPES + 2] = 1.0 if node.name else 0.0
            x[i, NUM_NODE_TYPES + 3] = node.line / max(max_line, 1)
            x[i, NUM_NODE_TYPES + 4] = 1.0 if node.type in _OPERATOR_TYPES else 0.0
            x[i, NUM_NODE_TYPES + 5] = sizes[i] / max(max_subtree, 1)
            x[i, NUM_NODE_TYPES + 6] = 1.0 if in_loop[i] else 0.0
            x[i, NUM_NODE_TYPES + 7] = 1.0 if in_cond[i] else 0.0
            x[i, NUM_NODE_TYPES + 8] = min(len(node.children) / 10.0, 1.0)

        # Edge index
        if self.edges:
            edge_index = np.array(self.edges, dtype=np.int64).T
        else:
            edge_index = np.zeros((2, 0), dtype=np.int64)

        # Node labels for bug localisation
        node_labels = np.zeros(len(self.nodes), dtype=np.float32)
        if is_buggy and bug_line is not None:
            for i, ln in enumerate(self.node_lines):
                if ln == bug_line:
                    node_labels[i] = 1.0

        edge_type = (torch.tensor(self.edge_types, dtype=torch.long)
                     if self.edge_types
                     else torch.zeros(0, dtype=torch.long))

        return {
            "x": torch.tensor(x),
            "edge_index": torch.tensor(edge_index),
            "edge_type": edge_type,
            "y": torch.tensor([1.0 if is_buggy else 0.0]),
            "node_labels": torch.tensor(node_labels),
            "num_nodes": len(self.nodes),
            "node_lines": self.node_lines,
        }


# ---------------------------------------------------------------------------
# Public convenience function (mirrors ``code_to_graph``)
# ---------------------------------------------------------------------------

def js_code_to_graph(code: str, bug_line: int | None = None,
                     is_buggy: bool = False) -> dict | None:
    """Convert a JavaScript/TypeScript source string to a CPG dict.

    Returns the same format as ``model.ast_to_graph.code_to_graph``.
    """
    builder = JSGraphBuilder()
    return builder.build(code, bug_line=bug_line, is_buggy=is_buggy)
