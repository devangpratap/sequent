"""
Training script for Sequent GNN.

Trains the GAT model on the synthetic dataset with dual objectives:
1. Graph-level: binary classification (buggy vs correct)
2. Node-level: bug localization (which nodes are the bug)

Loss = graph_loss + lambda * node_loss

Enhancements (enabled via flags):
- --curriculum: Curriculum learning (easy → medium → hard bug types)
- --augment: Graph data augmentation (edge dropout, node feature noise, graph mixup)
"""

import argparse
import json
import math
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


# ---------------------------------------------------------------------------
# Curriculum learning: bug type difficulty tiers
# ---------------------------------------------------------------------------
EASY_BUG_TYPES = {'off_by_one', 'wrong_operator', 'none_deref'}
MEDIUM_BUG_TYPES = {'boundary_error', 'integer_overflow', 'missing_return'}
HARD_BUG_TYPES = {
    'swap_and_or', 'remove_base_case', 'wrong_init_value',
    'wrong_variable', 'wrong_init', 'swap_args', 'remove_return',
    'flip_boolean', 'swap_plus_minus',
}


def get_curriculum_phase(epoch):
    """Return the curriculum phase for a given epoch.

    Phase 1 (epochs 1-30):  easy bugs only
    Phase 2 (epochs 31-60): easy + medium bugs
    Phase 3 (epochs 61+):   full dataset
    """
    if epoch <= 30:
        return 1
    elif epoch <= 60:
        return 2
    else:
        return 3


def filter_by_curriculum(data_list, phase):
    """Filter a list of PyG Data objects to only include bugs in the current phase.

    Non-buggy samples (y==0, no bug_type) are always included.
    """
    if phase >= 3:
        return data_list

    allowed = set(EASY_BUG_TYPES)
    if phase >= 2:
        allowed = allowed | MEDIUM_BUG_TYPES

    filtered = []
    for d in data_list:
        bug_type = getattr(d, 'bug_type', None)
        if bug_type is None:
            # Clean sample or unknown — always include
            filtered.append(d)
        elif bug_type in allowed:
            filtered.append(d)
        # else: skip (bug type not in current phase)
    return filtered


# ---------------------------------------------------------------------------
# Data augmentation transforms (training-time only)
# ---------------------------------------------------------------------------

def augment_graph(data, edge_drop_rate=0.1, noise_std=0.01):
    """Apply random edge dropout and node feature noise to a PyG Data object.

    Returns a *new* Data object (does not mutate the original).
    """
    from torch_geometric.data import Data

    # Clone tensors
    x = data.x.clone()
    edge_index = data.edge_index.clone()
    edge_type = data.edge_type.clone() if hasattr(data, 'edge_type') and data.edge_type is not None else None

    # --- Random edge dropout ---
    num_edges = edge_index.size(1)
    if num_edges > 0 and edge_drop_rate > 0:
        keep_mask = torch.rand(num_edges) > edge_drop_rate
        # Never drop ALL edges
        if keep_mask.sum() == 0:
            keep_mask[0] = True
        edge_index = edge_index[:, keep_mask]
        if edge_type is not None:
            edge_type = edge_type[keep_mask]

    # --- Random node feature noise ---
    if noise_std > 0:
        noise = torch.randn_like(x) * noise_std
        x = x + noise

    new_data = Data(
        x=x,
        edge_index=edge_index,
        y=data.y,
        node_labels=data.node_labels,
    )
    if edge_type is not None:
        new_data.edge_type = edge_type
    if hasattr(data, 'z3_label'):
        new_data.z3_label = data.z3_label
    if hasattr(data, 'bug_type'):
        new_data.bug_type = data.bug_type
    return new_data


# ---------------------------------------------------------------------------
# Graph-level mixup (applied after pooling, inside train_epoch)
# ---------------------------------------------------------------------------

def graph_mixup(graph_features, labels, alpha=0.2, mix_prob=0.3):
    """Mixup graph-level features and labels.

    With probability `mix_prob`, interpolate pairs of samples with different labels.

    Args:
        graph_features: [batch_size, feat_dim] — pooled graph features
        labels: [batch_size] — binary labels (0 or 1)
        alpha: Beta distribution parameter for mixing coefficient
        mix_prob: probability of applying mixup

    Returns:
        mixed_features, mixed_labels
    """
    if torch.rand(1).item() > mix_prob:
        return graph_features, labels

    batch_size = graph_features.size(0)
    if batch_size < 2:
        return graph_features, labels

    # Sample mixing coefficient from Beta(alpha, alpha)
    lam = np.random.beta(alpha, alpha)
    lam = max(lam, 1 - lam)  # ensure lam >= 0.5 so identity is dominant

    # Random permutation for pairing
    perm = torch.randperm(batch_size, device=graph_features.device)

    mixed_features = lam * graph_features + (1 - lam) * graph_features[perm]
    mixed_labels = lam * labels + (1 - lam) * labels[perm]

    return mixed_features, mixed_labels


# ---------------------------------------------------------------------------
# Learning rate schedule: linear warmup + cosine decay
# ---------------------------------------------------------------------------

class WarmupCosineScheduler:
    """Linear warmup for `warmup_epochs`, then cosine decay to `min_lr`."""

    def __init__(self, optimizer, warmup_epochs, total_epochs, base_lr, min_lr=1e-6):
        self.optimizer = optimizer
        self.warmup_epochs = warmup_epochs
        self.total_epochs = total_epochs
        self.base_lr = base_lr
        self.min_lr = min_lr

    def step(self, epoch):
        if epoch <= self.warmup_epochs:
            # Linear warmup
            lr = self.base_lr * epoch / max(self.warmup_epochs, 1)
        else:
            # Cosine decay
            progress = (epoch - self.warmup_epochs) / max(self.total_epochs - self.warmup_epochs, 1)
            lr = self.min_lr + 0.5 * (self.base_lr - self.min_lr) * (1 + math.cos(math.pi * progress))
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr
        return lr


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


def nt_xent_loss(z, z3_labels, temperature=0.07, hard_negative_weight=0.5):
    """
    NT-Xent contrastive loss with semi-hard negative mining.

    Positives: samples with the same z3_label (both verified or both counterexample).
    Samples with z3_label=2 (unknown) are excluded.

    Hard negative mining: negatives with high similarity to the anchor (close to the
    decision boundary) receive higher weight in the denominator, making the model
    focus on distinguishing the most confusing cases.

    Args:
        z: L2-normalized projection embeddings [batch_size, proj_dim]
        z3_labels: Z3 labels [batch_size] (0=verified, 1=counterexample, 2=unknown)
        temperature: softmax temperature (lower = sharper)
        hard_negative_weight: extra weight for semi-hard negatives (0 = standard NT-Xent)

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
    neg_mask = (~label_match) & self_mask

    # Need at least one positive per anchor
    has_positive = pos_mask.any(dim=1)
    if has_positive.sum() == 0:
        return torch.tensor(0.0, device=z.device)

    # For numerical stability
    sim_max, _ = sim.max(dim=1, keepdim=True)
    sim = sim - sim_max.detach()

    # --- Hard negative mining ---
    # Compute negative weights: upweight negatives with high similarity (semi-hard)
    # For each anchor, find the hardest positive similarity as the boundary
    exp_sim = torch.exp(sim)

    if hard_negative_weight > 0 and neg_mask.any():
        # Raw (unscaled) similarities for ranking
        raw_sim = torch.mm(z, z.t())  # [n, n], values in [-1, 1]

        # For each anchor, get the minimum positive similarity as the "boundary"
        pos_sims = raw_sim.clone()
        pos_sims[~pos_mask] = float('inf')
        min_pos_sim, _ = pos_sims.min(dim=1, keepdim=True)  # [n, 1]

        # Semi-hard negatives: negatives with similarity > min_positive_sim
        # (i.e., closer than the farthest positive — near the decision boundary)
        neg_sims = raw_sim.clone()
        neg_sims[~neg_mask] = float('-inf')
        is_semi_hard = (neg_sims >= min_pos_sim) & neg_mask  # [n, n]

        # Build weight matrix: 1.0 for all, + hard_negative_weight for semi-hard negatives
        neg_weights = torch.ones_like(sim)
        neg_weights[is_semi_hard] = 1.0 + hard_negative_weight

        # Apply weights to denominator
        weighted_exp_sim = exp_sim * self_mask.float() * neg_weights
    else:
        weighted_exp_sim = exp_sim * self_mask.float()

    log_denom = torch.log(weighted_exp_sim.sum(dim=1) + 1e-8)

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
                contrastive_weight=0.1, use_mixup=False):
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

        # --- Graph mixup (applied to predictions via label interpolation) ---
        graph_labels = batch.y.float()
        if use_mixup and graph_pred.size(0) >= 2:
            # We apply mixup at the prediction/label level (post-pooling effect)
            # by mixing the labels to match virtual mixed features
            mixed_preds, mixed_labels = graph_mixup(
                graph_pred.view(-1).unsqueeze(1), graph_labels, alpha=0.2, mix_prob=0.3
            )
            graph_loss = focal_loss(mixed_preds.view(-1), mixed_labels.view(-1), alpha=0.4, gamma=2.0)
        else:
            graph_loss = focal_loss(graph_pred.view(-1), graph_labels, alpha=0.4, gamma=2.0)

        # Node-level loss (weighted for sparse bug labels)
        node_losses = node_criterion(node_pred.view(-1), batch.node_labels.float())
        pos_weight = 10.0
        weights = torch.where(batch.node_labels > 0, pos_weight, 1.0)
        node_loss = (node_losses * weights).mean()

        # Contrastive loss with hard negative mining (only if z3_labels available)
        cl_loss = torch.tensor(0.0, device=device)
        if hasattr(batch, 'z3_label'):
            cl_loss = nt_xent_loss(z, batch.z3_label.view(-1), temperature=0.07,
                                   hard_negative_weight=0.5)

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


def parse_args():
    parser = argparse.ArgumentParser(description='Train Sequent GNN')
    parser.add_argument('--curriculum', action='store_true',
                        help='Enable curriculum learning (easy→medium→hard bug types)')
    parser.add_argument('--augment', action='store_true',
                        help='Enable graph data augmentation (edge dropout, node noise, mixup)')
    parser.add_argument('--epochs', type=int, default=200, help='Max training epochs')
    parser.add_argument('--batch-size', type=int, default=64, help='Batch size')
    parser.add_argument('--lr', type=float, default=0.001, help='Learning rate')
    parser.add_argument('--hidden', type=int, default=256, help='Hidden channels')
    parser.add_argument('--heads', type=int, default=8, help='Number of attention heads')
    parser.add_argument('--dropout', type=float, default=0.3, help='Dropout rate')
    parser.add_argument('--patience', type=int, default=25, help='Early stopping patience')
    parser.add_argument('--warmup-epochs', type=int, default=10,
                        help='Linear LR warmup epochs (used with --augment or --curriculum)')
    return parser.parse_args()


def main():
    args = parse_args()

    # Config
    DATASET_DIR = os.path.join(os.path.dirname(__file__), '..', 'dataset', 'generated')
    MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'checkpoints')
    os.makedirs(MODEL_DIR, exist_ok=True)

    EPOCHS = args.epochs
    BATCH_SIZE = args.batch_size
    LR = args.lr
    HIDDEN = args.hidden
    HEADS = args.heads
    DROPOUT = args.dropout
    NODE_LOSS_WEIGHT = 0.5
    PATIENCE = args.patience
    CONTRASTIVE_WEIGHT = 0.1  # lambda_2 for NT-Xent contrastive loss
    USE_CURRICULUM = args.curriculum
    USE_AUGMENT = args.augment
    WARMUP_EPOCHS = args.warmup_epochs

    device = torch.device('cuda' if torch.cuda.is_available() else
                          'mps' if torch.backends.mps.is_available() else 'cpu')
    print(f"Using device: {device}")
    if USE_CURRICULUM:
        print("Curriculum learning: ENABLED")
        print(f"  Phase 1 (epochs 1-30):  easy bugs   — {sorted(EASY_BUG_TYPES)}")
        print(f"  Phase 2 (epochs 31-60): + medium    — {sorted(MEDIUM_BUG_TYPES)}")
        print(f"  Phase 3 (epochs 61+):   full dataset — + {sorted(HARD_BUG_TYPES)}")
    if USE_AUGMENT:
        print("Data augmentation: ENABLED (edge dropout=10%, noise σ=0.01, mixup p=0.3)")
        print(f"LR schedule: linear warmup ({WARMUP_EPOCHS} epochs) + cosine decay")

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
    train_data_full = [build_pyg_data(g) for g in train_graphs]
    val_data = [build_pyg_data(g) for g in val_graphs]
    test_data = [build_pyg_data(g) for g in test_graphs]

    # Compute class weight for imbalanced data
    num_buggy = sum(1 for g in train_graphs if g['y'] == 1)
    num_clean = sum(1 for g in train_graphs if g['y'] == 0)
    pos_class_weight = max(num_buggy / max(num_clean, 1), 1.0)
    print(f"Class balance: {num_buggy} buggy, {num_clean} clean (weight={pos_class_weight:.2f})")

    # Validation and test loaders are always on the full dataset
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

    # LR schedule: warmup+cosine when augment is enabled, ReduceLROnPlateau otherwise
    use_warmup_cosine = USE_AUGMENT or USE_CURRICULUM
    if use_warmup_cosine:
        lr_scheduler = WarmupCosineScheduler(optimizer, WARMUP_EPOCHS, EPOCHS, LR, min_lr=1e-6)
        plateau_scheduler = None
        print(f"LR schedule: warmup({WARMUP_EPOCHS}) + cosine decay over {EPOCHS} epochs")
    else:
        lr_scheduler = None
        plateau_scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', patience=12, factor=0.5
        )

    # Training loop
    best_val_loss = float('inf')
    patience_counter = 0
    history = []
    prev_phase = 0

    print(f"\nTraining for up to {EPOCHS} epochs (patience={PATIENCE})...")
    print("-" * 80)

    for epoch in range(1, EPOCHS + 1):
        t0 = time.time()

        # --- LR warmup + cosine ---
        if lr_scheduler is not None:
            lr_scheduler.step(epoch)

        # --- Curriculum learning: rebuild train loader if phase changed ---
        if USE_CURRICULUM:
            phase = get_curriculum_phase(epoch)
            if phase != prev_phase:
                filtered_data = filter_by_curriculum(train_data_full, phase)
                print(f"  [Curriculum] Phase {phase}: {len(filtered_data)}/{len(train_data_full)} samples")
                prev_phase = phase
        else:
            filtered_data = train_data_full

        # --- Data augmentation: apply transforms ---
        if USE_AUGMENT:
            augmented_data = [augment_graph(d, edge_drop_rate=0.1, noise_std=0.01) for d in filtered_data]
        else:
            augmented_data = filtered_data

        train_loader = PyGDataLoader(augmented_data, batch_size=BATCH_SIZE, shuffle=True)

        train_loss, train_metrics = train_epoch(
            model, train_loader, optimizer, device, NODE_LOSS_WEIGHT, pos_class_weight,
            contrastive_weight=CONTRASTIVE_WEIGHT if has_z3 else 0.0,
            use_mixup=USE_AUGMENT,
        )
        val_loss, val_graph_metrics, val_node_metrics = evaluate(model, val_loader, device)

        if plateau_scheduler is not None:
            plateau_scheduler.step(val_loss)
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
        phase_str = f" | Ph{get_curriculum_phase(epoch)}" if USE_CURRICULUM else ""
        print(f"Epoch {epoch:3d} | "
              f"Train Loss: {train_loss:.4f} | "
              f"Val Loss: {val_loss:.4f} | "
              f"Train Acc: {train_metrics['accuracy']:.3f} | "
              f"Val Acc: {val_graph_metrics['accuracy']:.3f} | "
              f"Val F1: {val_graph_metrics['f1']:.3f} | "
              f"Node F1: {val_node_metrics['f1']:.3f}{cl_str}{phase_str} | "
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
                },
                'flags': {
                    'curriculum': USE_CURRICULUM,
                    'augment': USE_AUGMENT,
                },
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
