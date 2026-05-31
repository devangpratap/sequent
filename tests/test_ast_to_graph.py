"""Tests for the AST-to-CPG pipeline."""

import torch
import pytest

from model.ast_to_graph import code_to_graph, ASTGraphBuilder


def test_basic_function():
    code = "def add(a, b):\n    return a + b"
    g = code_to_graph(code)
    assert g is not None
    assert g['num_nodes'] > 0
    assert g['x'].shape[0] == g['num_nodes']
    assert g['edge_index'].shape[0] == 2


def test_edge_type_counts():
    """Edge types: 0=AST, 1=CFG, 2=DFG."""
    code = """
def foo(x):
    y = x + 1
    z = y * 2
    return z
"""
    g = code_to_graph(code)
    et = g['edge_type']
    assert et.shape[0] == g['edge_index'].shape[1]
    assert (et == 0).sum() > 0  # AST edges exist
    assert (et == 1).sum() > 0  # CFG edges exist (sequential stmts)
    assert (et == 2).sum() > 0  # DFG edges exist (y def→use, z def→use)


def test_cfg_edges_if_else():
    """If/else should create CFG branch edges."""
    code = """
def check(x):
    if x > 0:
        return 1
    else:
        return -1
"""
    g = code_to_graph(code)
    cfg_count = (g['edge_type'] == 1).sum().item()
    assert cfg_count >= 2  # at least if→body and if→else


def test_cfg_edges_loop_backedge():
    """Loops should create back-edges."""
    code = """
def count(n):
    total = 0
    for i in range(n):
        total += i
    return total
"""
    g = code_to_graph(code)
    cfg_count = (g['edge_type'] == 1).sum().item()
    assert cfg_count >= 2  # loop→body and body→loop back-edge


def test_buggy_labels():
    code = "def f():\n    x = 1\n    return x"
    g = code_to_graph(code, bug_line=2, is_buggy=True)
    assert g['y'].item() == 1.0
    assert g['node_labels'].sum() > 0


def test_clean_labels():
    code = "def f():\n    return 42"
    g = code_to_graph(code, is_buggy=False)
    assert g['y'].item() == 0.0
    assert g['node_labels'].sum() == 0


def test_syntax_error_returns_none():
    g = code_to_graph("def f(:\n    pass")
    assert g is None


def test_empty_code():
    """Empty string parses to a Module with 1 node — valid graph."""
    g = code_to_graph("")
    assert g is not None
    assert g['num_nodes'] == 1


def test_feature_dim():
    """Feature dim should be NUM_NODE_TYPES + 1 (unknown) + 8 (structural)."""
    from model.ast_to_graph import NUM_NODE_TYPES
    code = "def f():\n    return 1"
    g = code_to_graph(code)
    assert g['x'].shape[1] == NUM_NODE_TYPES + 1 + 8


def test_data_flow_edges():
    """Variable def→use should create DFG edges."""
    code = """
def f():
    x = 10
    return x
"""
    g = code_to_graph(code)
    dfg_count = (g['edge_type'] == 2).sum().item()
    assert dfg_count >= 1
