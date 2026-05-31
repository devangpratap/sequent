"""
Training script for Sequent GNN.

Trains the GAT model on the synthetic dataset with dual objectives:
1. Graph-level: binary classification (buggy vs correct)
2. Node-level: bug localization (which nodes are the bug)

Loss = graph_loss + lambda * node_loss
"""

import json
import os
import sys
import time

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import numpy as np

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.ast_to_graph import load_dataset_as_graphs, NUM_NODE_TYPES
from model.gnn import SequentGNN, build_pyg_data

try:
    from torch_geometric.loader import DataLoader as PyGDataLoader
    HAS_PYG_LOADER = True
except ImportError:
    HAS_PYG_LOADER = False


def compute_metrics(preds, labels, threshold=0.5):
    """Compute accuracy, precision, recall, F1."""
    binary_preds = (preds >= threshold).float()
    tp = ((binary_preds == 1) & (labels == 1)).sum().float()
    fp = ((binary_preds == 1) & (labels == 0)).sum().float()
    fn = ((binary_preds == 0) & (labels == 1)).sum().float()
    tn = ((binary_preds == 0) & (labels == 0)).sum().float()

    accuracy = (tp + tn) / (tp + tn + fp + fn + 1e-8)
    precision = tp / (tp + fp + 1e-8)
    recall = tp / (tp + fn + 1e-8)
    f1 = 2 * precision * recall / (precision + recall + 1e-8)

    return {
        'accuracy': accuracy.item(),
        'precision': precision.item(),
        'recall': recall.item(),
        'f1': f1.item(),
    }


def nt_xent_loss(z, z3_labels, temperature=0.07):
    """
    NT-Xent contrastive loss using Z3 outcomes as supervision.

    Positives: samples with the same z3_label (both verified or both counterexample).
    Samples with z3_label=2 (unknown) are excluded.

    Args:
        z: L2-normalized projection embeddings [batch_size, proj_dim]
        z3_labels: Z3 labels [batch_size] (0=verified, 1=counterexample, 2=unknown)
        temperature: softmax temperature (lower = sharper)

    Returns:
        Scalar contrastive loss, or 0 if not enough valid samples.
    """
    # Filter out unknown (label=2)
    mask = z3_labels != 2
    if mask.sum() < 2:
        return torch.tensor(0.0, device=z.device)

    z = z[mask]
    labels = z3_labels[mask]

    n = z.size(0)
    # Similarity matrix
    sim = torch.mm(z, z.t()) / temperature  # [n, n]

    # Positive mask: same z3 label (excluding self)
    label_match = labels.unsqueeze(0) == labels.unsqueeze(1)  # [n, n]
    self_mask = ~torch.eye(n, dtype=torch.bool, device=z.device)
    pos_mask = label_match & self_mask

    # Need at least one positive per anchor
    has_positive = pos_mask.any(dim=1)
    if has_positive.sum() == 0:
        return torch.tensor(0.0, device=z.device)

    # For numerical stability
    sim_max, _ = sim.max(dim=1, keepdim=True)
    sim = sim - sim_max.detach()

    # Denominator: all pairs except self
    exp_sim = torch.exp(sim) * self_mask.float()
    log_denom = torch.log(exp_sim.sum(dim=1) + 1e-8)

    # Numerator: mean log-prob over positives
    log_prob = sim - log_denom.unsqueeze(1)
    # Mean of log-prob for positive pairs per anchor
    pos_log_prob = (log_prob * pos_mask.float()).sum(dim=1) / (pos_mask.float().sum(dim=1) + 1e-8)

    # Only average over anchors that have positives
    loss = -pos_log_prob[has_positive].mean()
    return loss


def focal_loss(pred, target, alpha=0.25, gamma=2.0, label_smoothing=0.05):
    """Focal loss with label smoothing — handles imbalance + prevents overconfidence."""
    # Label smoothing: 0 → smooth, 1 → 1-smooth
    target_smooth = target * (1 - label_smoothing) + (1 - target) * label_smoothing
    bce = nn.functional.binary_cross_entropy(pred, target_smooth, reduction='none')
    pt = torch.where(target == 1, pred, 1 - pred)
    alpha_t = torch.where(target == 1, alpha, 1 - alpha)
    return (alpha_t * (1 - pt) ** gamma * bce).mean()


def train_epoch(model, loader, optimizer, device, node_loss_weight=0.5, pos_class_weight=1.0,
                contrastive_weight=0.1):
    model.train()
    total_loss = 0
    total_cl_loss = 0
    all_graph_preds = []
    all_graph_labels = []

    node_criterion = nn.BCELoss(reduction='none')

    for batch in loader:
        batch = batch.to(device)
        optimizer.zero_grad()

        edge_type = batch.edge_type if hasattr(batch, 'edge_type') else None
        graph_pred, node_pred, _, z = model(batch.x, batch.edge_index, batch.batch, edge_type=edge_type)

        # Focal loss for graph-level (handles imbalance + hard examples)
        graph_loss = focal_loss(graph_pred.view(-1), batch.y.float(), alpha=0.4, gamma=2.0)

        # Node-level loss (weighted for sparse bug labels)
        node_losses = node_criterion(node_pred.view(-1), batch.node_labels.float())
        pos_weight = 10.0
        weights = torch.where(batch.node_labels > 0, pos_weight, 1.0)
        node_loss = (node_losses * weights).mean()

        # Contrastive loss (only if z3_labels available)
        cl_loss = torch.tensor(0.0, device=device)
        if hasattr(batch, 'z3_label'):
            cl_loss = nt_xent_loss(z, batch.z3_label.view(-1), temperature=0.07)

        loss = graph_loss + node_loss_weight * node_loss + contrastive_weight * cl_loss
        loss.backward()

        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

        optimizer.step()
        total_loss += loss.item()
        total_cl_loss += cl_loss.item()

        all_graph_preds.append(graph_pred.detach().cpu().view(-1))
        all_graph_labels.append(batch.y.detach().cpu().float())

    all_graph_preds = torch.cat(all_graph_preds)
    all_graph_labels = torch.cat(all_graph_labels)
    metrics = compute_metrics(all_graph_preds, all_graph_labels)
    metrics['contrastive_loss'] = total_cl_loss / len(loader)

    return total_loss / len(loader), metrics


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    total_loss = 0
    all_graph_preds = []
    all_graph_labels = []
    all_node_preds = []
    all_node_labels = []

    graph_criterion = nn.BCELoss()
    node_criterion = nn.BCELoss()

    for batch in loader:
        batch = batch.to(device)
        edge_type = batch.edge_type if hasattr(batch, 'edge_type') else None
        graph_pred, node_pred, _, _ = model(batch.x, batch.edge_index, batch.batch, edge_type=edge_type)

        graph_loss = graph_criterion(graph_pred.view(-1), batch.y.float())
        node_loss = node_criterion(node_pred.view(-1), batch.node_labels.float())
        total_loss += (graph_loss + 0.5 * node_loss).item()

        all_graph_preds.append(graph_pred.cpu().view(-1))
        all_graph_labels.append(batch.y.cpu().float())
        all_node_preds.append(node_pred.cpu().view(-1))
        all_node_labels.append(batch.node_labels.cpu().float())

    all_graph_preds = torch.cat(all_graph_preds)
    all_graph_labels = torch.cat(all_graph_labels)
    graph_metrics = compute_metrics(all_graph_preds, all_graph_labels)

    all_node_preds = torch.cat(all_node_preds)
    all_node_labels = torch.cat(all_node_labels)
    node_metrics = compute_metrics(all_node_preds, all_node_labels)

    return total_loss / len(loader), graph_metrics, node_metrics


def main():
    # Config
    DATASET_DIR = os.path.join(os.path.dirname(__file__), '..', 'dataset', 'generated')
    MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'checkpoints')
    os.makedirs(MODEL_DIR, exist_ok=True)

    EPOCHS = 200
    BATCH_SIZE = 64
    LR = 0.001
    HIDDEN = 256
    HEADS = 8
    DROPOUT = 0.3
    NODE_LOSS_WEIGHT = 0.5
    PATIENCE = 25  # early stopping
    CONTRASTIVE_WEIGHT = 0.1  # lambda_2 for NT-Xent contrastive loss

    device = torch.device('cuda' if torch.cuda.is_available() else
                          'mps' if torch.backends.mps.is_available() else 'cpu')
    print(f"Using device: {device}")

    # Load data — prefer z3-labeled versions if available
    print("Loading dataset...")
    def _pick_dataset(split):
        z3_path = os.path.join(DATASET_DIR, f'{split}_z3.json')
        plain_path = os.path.join(DATASET_DIR, f'{split}.json')
        if os.path.exists(z3_path):
            print(f"  {split}: using z3-labeled dataset")
            return z3_path
        return plain_path

    train_graphs = load_dataset_as_graphs(_pick_dataset('train'))
    val_graphs = load_dataset_as_graphs(_pick_dataset('val'))
    test_graphs = load_dataset_as_graphs(_pick_dataset('test'))

    has_z3 = any('z3_label' in g for g in train_graphs)
    if has_z3:
        n_z3 = sum(1 for g in train_graphs if 'z3_label' in g)
        print(f"  Z3 labels present on {n_z3}/{len(train_graphs)} training samples")
    else:
        print("  No Z3 labels found — contrastive loss will be skipped")

    print(f"Train: {len(train_graphs)}, Val: {len(val_graphs)}, Test: {len(test_graphs)}")

    # Convert to PyG Data objects
    train_data = [build_pyg_data(g) for g in train_graphs]
    val_data = [build_pyg_data(g) for g in val_graphs]
    test_data = [build_pyg_data(g) for g in test_graphs]

    # Compute class weight for imbalanced data
    num_buggy = sum(1 for g in train_graphs if g['y'] == 1)
    num_clean = sum(1 for g in train_graphs if g['y'] == 0)
    pos_class_weight = max(num_buggy / max(num_clean, 1), 1.0)
    print(f"Class balance: {num_buggy} buggy, {num_clean} clean (weight={pos_class_weight:.2f})")

    train_loader = PyGDataLoader(train_data, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = PyGDataLoader(val_data, batch_size=BATCH_SIZE)
    test_loader = PyGDataLoader(test_data, batch_size=BATCH_SIZE)

    # Model
    in_channels = NUM_NODE_TYPES + 1 + 8  # onehot + unknown + extra features
    model = SequentGNN(
        in_channels=in_channels,
        hidden_channels=HIDDEN,
        num_heads=HEADS,
        dropout=DROPOUT,
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {total_params:,}")

    optimizer = optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', patience=12, factor=0.5)

    # Training loop
    best_val_loss = float('inf')
    patience_counter = 0
    history = []

    print(f"\nTraining for up to {EPOCHS} epochs (patience={PATIENCE})...")
    print("-" * 80)

    for epoch in range(1, EPOCHS + 1):
        t0 = time.time()

        train_loss, train_metrics = train_epoch(
            model, train_loader, optimizer, device, NODE_LOSS_WEIGHT, pos_class_weight,
            contrastive_weight=CONTRASTIVE_WEIGHT if has_z3 else 0.0
        )
        val_loss, val_graph_metrics, val_node_metrics = evaluate(model, val_loader, device)

        scheduler.step(val_loss)
        elapsed = time.time() - t0

        history.append({
            'epoch': epoch,
            'train_loss': train_loss,
            'val_loss': val_loss,
            'train_acc': train_metrics['accuracy'],
            'val_acc': val_graph_metrics['accuracy'],
            'val_f1': val_graph_metrics['f1'],
            'val_node_f1': val_node_metrics['f1'],
            'contrastive_loss': train_metrics.get('contrastive_loss', 0),
            'lr': optimizer.param_groups[0]['lr'],
        })

        cl_str = f" | CL: {train_metrics.get('contrastive_loss', 0):.4f}" if has_z3 else ""
        print(f"Epoch {epoch:3d} | "
              f"Train Loss: {train_loss:.4f} | "
              f"Val Loss: {val_loss:.4f} | "
              f"Train Acc: {train_metrics['accuracy']:.3f} | "
              f"Val Acc: {val_graph_metrics['accuracy']:.3f} | "
              f"Val F1: {val_graph_metrics['f1']:.3f} | "
              f"Node F1: {val_node_metrics['f1']:.3f}{cl_str} | "
              f"LR: {optimizer.param_groups[0]['lr']:.6f} | "
              f"{elapsed:.1f}s")

        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_loss': val_loss,
                'val_metrics': val_graph_metrics,
                'config': {
                    'in_channels': in_channels,
                    'hidden_channels': HIDDEN,
                    'num_heads': HEADS,
                    'dropout': DROPOUT,
                    'num_edge_types': 3,
                    'edge_embed_dim': 16,
                }
            }, os.path.join(MODEL_DIR, 'best_model.pt'))
            print(f"  → Saved best model (val_loss={val_loss:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print(f"\nEarly stopping at epoch {epoch}")
                break

    # Final evaluation on test set
    print("\n" + "=" * 80)
    print("Final evaluation on test set:")
    checkpoint = torch.load(os.path.join(MODEL_DIR, 'best_model.pt'), map_location=device, weights_only=True)
    model.load_state_dict(checkpoint['model_state_dict'])

    test_loss, test_graph_metrics, test_node_metrics = evaluate(model, test_loader, device)
    print(f"Test Loss: {test_loss:.4f}")
    print(f"Graph-level — Acc: {test_graph_metrics['accuracy']:.3f}, "
          f"P: {test_graph_metrics['precision']:.3f}, "
          f"R: {test_graph_metrics['recall']:.3f}, "
          f"F1: {test_graph_metrics['f1']:.3f}")
    print(f"Node-level  — Acc: {test_node_metrics['accuracy']:.3f}, "
          f"P: {test_node_metrics['precision']:.3f}, "
          f"R: {test_node_metrics['recall']:.3f}, "
          f"F1: {test_node_metrics['f1']:.3f}")

    # Save training history
    with open(os.path.join(MODEL_DIR, 'training_history.json'), 'w') as f:
        json.dump(history, f, indent=2)

    print(f"\nTraining history saved to {MODEL_DIR}/training_history.json")
    print(f"Best model saved to {MODEL_DIR}/best_model.pt")


if __name__ == '__main__':
    main()
