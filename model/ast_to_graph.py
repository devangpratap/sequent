"""
AST-to-Graph Pipeline for Sequent.

Converts Python source code into a Code Property Graph (CPG):
- Nodes: AST nodes (type-encoded)
- Edges: parent↔child (AST) + control flow (CFG) + data flow (def→use)
- Node features: [node_type_onehot, depth, has_identifier, position_encoding, ...]
- Graph label: 0 (correct) or 1 (buggy)
- Node labels: 0 (normal) or 1 (bug location) for node-level prediction
"""

import ast
import json
from typing import Optional

import torch
import numpy as np

# AST node types we care about — covers Python's core grammar
AST_NODE_TYPES = [
    'Module', 'FunctionDef', 'AsyncFunctionDef', 'ClassDef', 'Return',
    'Delete', 'Assign', 'AugAssign', 'AnnAssign', 'For', 'AsyncFor',
    'While', 'If', 'With', 'AsyncWith', 'Raise', 'Try', 'TryStar',
    'Assert', 'Import', 'ImportFrom', 'Global', 'Nonlocal', 'Expr',
    'Pass', 'Break', 'Continue',
    # Expressions
    'BoolOp', 'NamedExpr', 'BinOp', 'UnaryOp', 'Lambda', 'IfExp',
    'Dict', 'Set', 'ListComp', 'SetComp', 'DictComp', 'GeneratorExp',
    'Await', 'Yield', 'YieldFrom', 'Compare', 'Call', 'FormattedValue',
    'JoinedStr', 'Constant', 'Attribute', 'Subscript', 'Starred',
    'Name', 'List', 'Tuple', 'Slice',
    # Operators (encoded as nodes for richer representation)
    'Add', 'Sub', 'Mult', 'Div', 'Mod', 'Pow', 'LShift', 'RShift',
    'BitOr', 'BitXor', 'BitAnd', 'FloorDiv', 'MatMult',
    'And', 'Or', 'Not', 'Invert', 'UAdd', 'USub',
    'Eq', 'NotEq', 'Lt', 'LtE', 'Gt', 'GtE', 'Is', 'IsNot', 'In', 'NotIn',
    # Other
    'arguments', 'arg', 'keyword', 'alias', 'comprehension',
    'ExceptHandler', 'MatchValue', 'MatchSingleton',
]

NODE_TYPE_TO_IDX = {t: i for i, t in enumerate(AST_NODE_TYPES)}
NUM_NODE_TYPES = len(AST_NODE_TYPES)
UNKNOWN_TYPE_IDX = NUM_NODE_TYPES  # For any node type not in our list


def get_node_type_idx(node) -> int:
    type_name = type(node).__name__
    return NODE_TYPE_TO_IDX.get(type_name, UNKNOWN_TYPE_IDX)


class ASTGraphBuilder:
    """Converts a Python AST into a graph with node features and edges."""

    # Edge type constants
    EDGE_AST = 0
    EDGE_CFG = 1
    EDGE_DFG = 2
    NUM_EDGE_TYPES = 3

    def __init__(self):
        self.nodes = []         # list of (ast_node, depth, node_idx)
        self.edges = []         # list of (src_idx, dst_idx)
        self.edge_types = []    # parallel to self.edges: 0=AST, 1=CFG, 2=DFG
        self.node_features = [] # list of feature vectors
        self.node_lines = []    # line number for each node
        self.var_defs = {}      # variable_name → defining node index (for data flow)
        self._node_map = {}     # id(ast_node) → graph node index

    def _compute_subtree_sizes(self):
        """Compute subtree size for each node (number of descendants + 1)."""
        sizes = [1] * len(self.nodes)
        # Build adjacency: parent → children (only downward edges)
        children = {i: [] for i in range(len(self.nodes))}
        for src, dst in self.edges:
            # In our edges, parent→child was added first, so src < dst means downward
            if src < dst:
                children[src].append(dst)
        # Bottom-up: reverse order
        for i in range(len(self.nodes) - 1, -1, -1):
            for c in children[i]:
                sizes[i] += sizes[c]
        return sizes

    def _compute_context_flags(self, tree):
        """For each node index, compute: is_in_loop, is_in_conditional."""
        in_loop = [False] * len(self.nodes)
        in_cond = [False] * len(self.nodes)

        # Walk the AST and track context
        def _mark(node, loop_ctx=False, cond_ctx=False):
            # Find this node's index
            for i, (n, _, _) in enumerate(self.nodes):
                if n is node:
                    in_loop[i] = loop_ctx
                    in_cond[i] = cond_ctx
                    break

            new_loop = loop_ctx or isinstance(node, (ast.For, ast.While, ast.AsyncFor))
            new_cond = cond_ctx or isinstance(node, ast.If)

            for child in ast.iter_child_nodes(node):
                _mark(child, new_loop, new_cond)

        _mark(tree)
        return in_loop, in_cond

    def build(self, code: str, bug_line: Optional[int] = None, is_buggy: bool = False):
        """
        Build graph from Python source code.

        Returns dict with:
            - x: node feature tensor [num_nodes, feature_dim]
            - edge_index: edge tensor [2, num_edges]
            - y: graph label (0 or 1)
            - node_labels: per-node labels [num_nodes]
            - num_nodes: int
        """
        self.nodes = []
        self.edges = []
        self.edge_types = []
        self.node_features = []
        self.node_lines = []
        self.var_defs = {}
        self._node_map = {}

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return None

        # Walk AST and build graph
        self._visit(tree, depth=0, parent_idx=None)

        if len(self.nodes) == 0:
            return None

        # Build control flow edges (CFG)
        self._add_cfg_edges(tree)

        # Build data flow edges (variable def → use)
        self._add_data_flow_edges(tree)

        # Compute structural features
        subtree_sizes = self._compute_subtree_sizes()
        max_subtree = max(subtree_sizes) if subtree_sizes else 1
        in_loop, in_cond = self._compute_context_flags(tree)

        # Compute parent type for each node
        parent_types = [UNKNOWN_TYPE_IDX] * len(self.nodes)
        for src, dst in self.edges:
            if src < dst:  # parent→child direction
                parent_node = self.nodes[src][0]
                parent_types[dst] = get_node_type_idx(parent_node)

        # Feature matrix: onehot + unknown + [depth, has_id, line_norm, is_operator, subtree_size, in_loop, in_cond, num_children]
        feature_dim = NUM_NODE_TYPES + 1 + 8
        x = np.zeros((len(self.nodes), feature_dim), dtype=np.float32)

        for i, (node, depth, _) in enumerate(self.nodes):
            type_idx = get_node_type_idx(node)
            if type_idx < NUM_NODE_TYPES:
                x[i, type_idx] = 1.0
            else:
                x[i, NUM_NODE_TYPES] = 1.0  # unknown flag

            # Original features
            max_depth = max(d for _, d, _ in self.nodes) if self.nodes else 1
            x[i, NUM_NODE_TYPES + 1] = depth / max(max_depth, 1)  # normalized depth
            x[i, NUM_NODE_TYPES + 2] = 1.0 if hasattr(node, 'id') else 0.0  # has identifier
            line = getattr(node, 'lineno', 0)
            max_line = max(self.node_lines) if self.node_lines else 1
            x[i, NUM_NODE_TYPES + 3] = line / max(max_line, 1)  # normalized line position
            is_op = type(node).__name__ in [
                'Add', 'Sub', 'Mult', 'Div', 'Mod', 'FloorDiv',
                'Lt', 'LtE', 'Gt', 'GtE', 'Eq', 'NotEq',
                'And', 'Or', 'Not',
            ]
            x[i, NUM_NODE_TYPES + 4] = 1.0 if is_op else 0.0

            # New structural features
            x[i, NUM_NODE_TYPES + 5] = subtree_sizes[i] / max(max_subtree, 1)  # normalized subtree size
            x[i, NUM_NODE_TYPES + 6] = 1.0 if in_loop[i] else 0.0  # is inside a loop
            x[i, NUM_NODE_TYPES + 7] = 1.0 if in_cond[i] else 0.0  # is inside a conditional
            num_children = len(list(ast.iter_child_nodes(node))) if isinstance(node, ast.AST) else 0
            x[i, NUM_NODE_TYPES + 8] = min(num_children / 10.0, 1.0)  # normalized child count

        # Edge index
        if self.edges:
            edge_index = np.array(self.edges, dtype=np.int64).T  # [2, num_edges]
        else:
            edge_index = np.zeros((2, 0), dtype=np.int64)

        # Node labels for bug localization
        node_labels = np.zeros(len(self.nodes), dtype=np.float32)
        if is_buggy and bug_line is not None:
            for i, line in enumerate(self.node_lines):
                if line == bug_line:
                    node_labels[i] = 1.0

        # Edge type tensor
        edge_type = torch.tensor(self.edge_types, dtype=torch.long) if self.edge_types else torch.zeros(0, dtype=torch.long)

        return {
            'x': torch.tensor(x),
            'edge_index': torch.tensor(edge_index),
            'edge_type': edge_type,
            'y': torch.tensor([1.0 if is_buggy else 0.0]),
            'node_labels': torch.tensor(node_labels),
            'num_nodes': len(self.nodes),
            'node_lines': self.node_lines,
        }

    def _visit(self, node, depth: int, parent_idx: Optional[int]):
        """Recursively visit AST nodes, adding them to the graph."""
        idx = len(self.nodes)
        self.nodes.append((node, depth, idx))
        self.node_lines.append(getattr(node, 'lineno', 0))
        self._node_map[id(node)] = idx

        # Track variable definitions
        if isinstance(node, ast.Name) and isinstance(getattr(node, 'ctx', None), ast.Store):
            self.var_defs[node.id] = idx

        # Add edge from parent (AST structural edges)
        if parent_idx is not None:
            self.edges.append((parent_idx, idx))
            self.edge_types.append(self.EDGE_AST)
            self.edges.append((idx, parent_idx))  # bidirectional
            self.edge_types.append(self.EDGE_AST)

        # Visit children
        for child in ast.iter_child_nodes(node):
            self._visit(child, depth + 1, idx)

        # Also add operator nodes as explicit children for richer representation
        if isinstance(node, ast.BinOp):
            self._visit(node.op, depth + 1, idx)
        elif isinstance(node, ast.UnaryOp):
            self._visit(node.op, depth + 1, idx)
        elif isinstance(node, ast.BoolOp):
            self._visit(node.op, depth + 1, idx)
        elif isinstance(node, ast.Compare):
            for op in node.ops:
                self._visit(op, depth + 1, idx)

    def _add_cfg_edges(self, tree):
        """Add control flow graph edges to form a Code Property Graph."""
        STMT_TYPES = (ast.stmt,)

        def _get_idx(node):
            return self._node_map.get(id(node))

        def _add_cfg_edge(src_node, dst_node):
            src = _get_idx(src_node)
            dst = _get_idx(dst_node)
            if src is not None and dst is not None and src != dst:
                self.edges.append((src, dst))
                self.edge_types.append(self.EDGE_CFG)

        def _process_body(stmts):
            """Add sequential flow edges within a statement block."""
            for i in range(len(stmts) - 1):
                _add_cfg_edge(stmts[i], stmts[i + 1])

            for stmt in stmts:
                _process_stmt(stmt)

        def _process_stmt(node):
            if isinstance(node, ast.If):
                # Condition → first stmt in body
                if node.body:
                    _add_cfg_edge(node, node.body[0])
                # Condition → first stmt in orelse (else/elif)
                if node.orelse:
                    _add_cfg_edge(node, node.orelse[0])
                _process_body(node.body)
                _process_body(node.orelse)

            elif isinstance(node, (ast.For, ast.AsyncFor)):
                # Loop header → first stmt in body
                if node.body:
                    _add_cfg_edge(node, node.body[0])
                # Back-edge: last stmt in body → loop header
                if node.body:
                    _add_cfg_edge(node.body[-1], node)
                # Loop header → first stmt in orelse (for-else)
                if node.orelse:
                    _add_cfg_edge(node, node.orelse[0])
                _process_body(node.body)
                _process_body(node.orelse)

            elif isinstance(node, ast.While):
                # Loop header → first stmt in body
                if node.body:
                    _add_cfg_edge(node, node.body[0])
                # Back-edge: last stmt in body → loop header
                if node.body:
                    _add_cfg_edge(node.body[-1], node)
                if node.orelse:
                    _add_cfg_edge(node, node.orelse[0])
                _process_body(node.body)
                _process_body(node.orelse)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Function entry → first stmt
                if node.body:
                    _add_cfg_edge(node, node.body[0])
                _process_body(node.body)

            elif isinstance(node, ast.Try):
                if node.body:
                    _add_cfg_edge(node, node.body[0])
                _process_body(node.body)
                for handler in node.handlers:
                    # Try → each except handler
                    _add_cfg_edge(node, handler)
                    if handler.body:
                        _add_cfg_edge(handler, handler.body[0])
                    _process_body(handler.body)
                _process_body(node.orelse)
                _process_body(node.finalbody)

            elif isinstance(node, ast.With) or isinstance(node, ast.AsyncWith):
                if node.body:
                    _add_cfg_edge(node, node.body[0])
                _process_body(node.body)

        # Start from module body
        if isinstance(tree, ast.Module):
            _process_body(tree.body)
        elif isinstance(tree, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _process_stmt(tree)

    def _add_data_flow_edges(self, tree):
        """Add edges from variable definitions to their uses."""
        for node_info in self.nodes:
            node = node_info[0]
            idx = node_info[2]
            if isinstance(node, ast.Name) and isinstance(getattr(node, 'ctx', None), ast.Load):
                if node.id in self.var_defs:
                    def_idx = self.var_defs[node.id]
                    if def_idx != idx:
                        self.edges.append((def_idx, idx))  # def → use
                        self.edge_types.append(self.EDGE_DFG)


def code_to_graph(code: str, bug_line: Optional[int] = None, is_buggy: bool = False):
    """Convenience function to convert code string to graph."""
    builder = ASTGraphBuilder()
    return builder.build(code, bug_line, is_buggy)


def load_dataset_as_graphs(json_path: str) -> list:
    """Load a JSON dataset file and convert all samples to graphs."""
    with open(json_path) as f:
        samples = json.load(f)

    graphs = []
    skipped = 0
    for sample in samples:
        graph = code_to_graph(
            code=sample['code'],
            bug_line=sample.get('bug_line'),
            is_buggy=sample.get('is_buggy', False),
        )
        if graph is not None:
            graph['sample_id'] = sample['id']
            graph['bug_type'] = sample.get('bug_type')
            if 'z3_label' in sample:
                graph['z3_label'] = torch.tensor([sample['z3_label']], dtype=torch.long)
            graphs.append(graph)
        else:
            skipped += 1

    if skipped > 0:
        print(f"Warning: skipped {skipped}/{len(samples)} samples (parse errors)")

    return graphs
