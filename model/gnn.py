"""
Graph Attention Network (GAT) for Sequent.

Dual-task model:
1. Graph-level classification: Is this function buggy? (binary)
2. Node-level classification: Which node is the bug? (per-node binary)

Architecture:
    Input features → GAT Layer 1 → GAT Layer 2 → GAT Layer 3
        ├─→ Global mean/max pool → MLP → graph_pred (buggy/correct)
        └─→ Node MLP → node_pred (bug location per node)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from torch_geometric.nn import GATv2Conv, global_mean_pool, global_max_pool
    from torch_geometric.data import Data, Batch
    HAS_PYG = True
except ImportError:
    HAS_PYG = False


class SequentGNN(nn.Module):
    def __init__(
        self,
        in_channels: int = 100,
        hidden_channels: int = 128,
        num_heads: int = 4,
        dropout: float = 0.3,
        num_edge_types: int = 3,
        edge_embed_dim: int = 16,
    ):
        super().__init__()

        # Edge type embedding (AST=0, CFG=1, DFG=2)
        self.edge_embedding = nn.Embedding(num_edge_types, edge_embed_dim)

        # GATv2 layers with edge features (more expressive dynamic attention)
        self.conv1 = GATv2Conv(in_channels, hidden_channels, heads=num_heads, dropout=dropout, concat=True, edge_dim=edge_embed_dim)
        self.conv2 = GATv2Conv(hidden_channels * num_heads, hidden_channels, heads=num_heads, dropout=dropout, concat=True, edge_dim=edge_embed_dim)
        self.conv3 = GATv2Conv(hidden_channels * num_heads, hidden_channels, heads=1, dropout=dropout, concat=False, edge_dim=edge_embed_dim)

        self.bn1 = nn.BatchNorm1d(hidden_channels * num_heads)
        self.bn2 = nn.BatchNorm1d(hidden_channels * num_heads)
        self.bn3 = nn.BatchNorm1d(hidden_channels)

        # Graph-level classifier (buggy or not)
        self.graph_mlp = nn.Sequential(
            nn.Linear(hidden_channels * 2, hidden_channels),  # *2 for mean+max pool
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_channels, 1),
        )

        # Node-level classifier (bug location)
        self.node_mlp = nn.Sequential(
            nn.Linear(hidden_channels, hidden_channels // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_channels // 2, 1),
        )

        # Projection head for contrastive learning (maps graph features → unit sphere)
        proj_dim = hidden_channels // 2
        self.projection_head = nn.Sequential(
            nn.Linear(hidden_channels * 2, hidden_channels),
            nn.ReLU(),
            nn.Linear(hidden_channels, proj_dim),
        )

        self.dropout = dropout

    def forward(self, x, edge_index, batch=None, edge_type=None):
        """
        Args:
            x: Node features [num_nodes, in_channels]
            edge_index: Edge indices [2, num_edges]
            batch: Batch assignment vector [num_nodes] (for batched graphs)
            edge_type: Edge type indices [num_edges] (0=AST, 1=CFG, 2=DFG)

        Returns:
            graph_pred: [batch_size, 1] — probability function is buggy
            node_pred: [num_nodes, 1] — probability each node is bug location
            node_embeddings: [num_nodes, hidden] — for visualization
            z: [batch_size, proj_dim] — contrastive projection
        """
        if batch is None:
            batch = torch.zeros(x.size(0), dtype=torch.long, device=x.device)

        # Edge type embeddings
        edge_attr = None
        if edge_type is not None:
            edge_attr = self.edge_embedding(edge_type)

        # GAT layers with edge-aware attention
        h, attn1 = self.conv1(x, edge_index, edge_attr=edge_attr, return_attention_weights=True)
        h = self.bn1(h)
        h = F.elu(h)
        h = F.dropout(h, p=self.dropout, training=self.training)

        h, attn2 = self.conv2(h, edge_index, edge_attr=edge_attr, return_attention_weights=True)
        h = self.bn2(h)
        h = F.elu(h)
        h = F.dropout(h, p=self.dropout, training=self.training)

        h, attn3 = self.conv3(h, edge_index, edge_attr=edge_attr, return_attention_weights=True)
        h = self.bn3(h)
        h = F.elu(h)

        # Store attention weights for interpretability (last layer, single head)
        self._last_attention = attn3

        node_embeddings = h  # Save for visualization

        # Graph-level prediction
        pool_mean = global_mean_pool(h, batch)
        pool_max = global_max_pool(h, batch)
        graph_features = torch.cat([pool_mean, pool_max], dim=1)
        graph_pred = torch.sigmoid(self.graph_mlp(graph_features))

        # Node-level prediction
        node_pred = torch.sigmoid(self.node_mlp(h))

        # Contrastive projection (L2-normalized for NT-Xent)
        z = self.projection_head(graph_features)
        z = F.normalize(z, dim=1)

        return graph_pred, node_pred, node_embeddings, z

    def get_attention_weights(self):
        """Return last-layer attention weights for interpretability.

        Returns (edge_index, attention_weights) from the final GATv2 layer,
        or None if no forward pass has been run yet.
        """
        if hasattr(self, '_last_attention') and self._last_attention is not None:
            edge_index, alpha = self._last_attention
            return edge_index.detach().cpu(), alpha.detach().cpu()
        return None


def build_pyg_data(graph_dict: dict) -> "Data":
    """Convert our graph dict to a PyTorch Geometric Data object."""
    data = Data(
        x=graph_dict['x'],
        edge_index=graph_dict['edge_index'],
        y=graph_dict['y'],
        node_labels=graph_dict['node_labels'],
    )
    if 'edge_type' in graph_dict:
        data.edge_type = graph_dict['edge_type']
    if 'z3_label' in graph_dict:
        data.z3_label = graph_dict['z3_label']
    if 'bug_type' in graph_dict and graph_dict['bug_type'] is not None:
        data.bug_type = graph_dict['bug_type']
    return data


def collate_graphs(graph_dicts: list) -> "Batch":
    """Convert a list of graph dicts into a batched PyG object."""
    data_list = [build_pyg_data(g) for g in graph_dicts]
    return Batch.from_data_list(data_list)
