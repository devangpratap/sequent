"""Tests for the GNN model."""

import torch
import pytest

from model.gnn import SequentGNN, build_pyg_data
from model.ast_to_graph import code_to_graph, NUM_NODE_TYPES


@pytest.fixture
def model():
    return SequentGNN(
        in_channels=NUM_NODE_TYPES + 1 + 8,
        hidden_channels=64,
        num_heads=2,
        dropout=0.1,
    )


@pytest.fixture
def sample_graph():
    code = "def add(a, b):\n    return a + b"
    return code_to_graph(code)


def test_forward_shape(model, sample_graph):
    x = sample_graph['x']
    ei = sample_graph['edge_index']
    et = sample_graph['edge_type']
    graph_pred, node_pred, embeddings, z = model(x, ei, edge_type=et)

    assert graph_pred.shape == (1, 1)
    assert node_pred.shape == (sample_graph['num_nodes'], 1)
    assert embeddings.shape == (sample_graph['num_nodes'], 64)
    assert z.shape == (1, 32)  # hidden//2 = 64//2


def test_forward_no_edge_type(model, sample_graph):
    """Model should work without edge types (backwards compat)."""
    x = sample_graph['x']
    ei = sample_graph['edge_index']
    graph_pred, node_pred, _, z = model(x, ei)

    assert graph_pred.shape == (1, 1)
    assert 0 <= graph_pred.item() <= 1


def test_projection_normalized(model, sample_graph):
    """Contrastive projection should be L2-normalized."""
    x = sample_graph['x']
    ei = sample_graph['edge_index']
    _, _, _, z = model(x, ei)

    norm = torch.norm(z, dim=1)
    assert torch.allclose(norm, torch.ones_like(norm), atol=1e-5)


def test_attention_weights(model, sample_graph):
    """Attention should be extractable after forward pass."""
    x = sample_graph['x']
    ei = sample_graph['edge_index']
    et = sample_graph['edge_type']
    model(x, ei, edge_type=et)

    attn = model.get_attention_weights()
    assert attn is not None
    edge_index, alpha = attn
    assert edge_index.shape[0] == 2
    assert alpha.shape[0] == edge_index.shape[1]


def test_build_pyg_data(sample_graph):
    data = build_pyg_data(sample_graph)
    assert hasattr(data, 'x')
    assert hasattr(data, 'edge_index')
    assert hasattr(data, 'y')
    assert hasattr(data, 'node_labels')
    assert hasattr(data, 'edge_type')


def test_build_pyg_data_with_z3_label(sample_graph):
    sample_graph['z3_label'] = torch.tensor([0], dtype=torch.long)
    data = build_pyg_data(sample_graph)
    assert hasattr(data, 'z3_label')
    assert data.z3_label.item() == 0
