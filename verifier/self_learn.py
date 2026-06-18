"""
Self-Learning Loop for Sequent — AlphaGo-style recursive self-improvement.

The loop:
1. ANALYZE: GNN proposes bugs on real code
2. VERIFY:  Z3 produces ground-truth verdicts (verified / counterexample)
3. COLLECT: (code, Z3 verdict) pairs stored as experience
4. LEARN:   GNN fine-tunes on accumulated experience
5. REPEAT:  Better GNN → better proposals → better training data → ...

The key insight: Z3 is a perfect oracle. Every time Sequent runs, Z3 gives
free ground-truth labels. The GNN learns from these labels and gets smarter
over time — without any human annotation.
"""

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from typing import Optional

import torch
import numpy as np


# Default experience directory
DEFAULT_EXPERIENCE_DIR = os.path.expanduser("~/.sequent/experience")
DEFAULT_MODEL_DIR = os.path.expanduser("~/.sequent/models")


@dataclass
class Experience:
    """A single training experience from a real verification run."""
    code: str
    function_name: str
    is_buggy: bool                    # Z3 ground truth
    z3_label: int                     # 0=verified, 1=counterexample, 2=unknown
    gnn_confidence: float             # what the GNN predicted
    gnn_was_correct: bool             # did GNN agree with Z3?
    bug_lines: list[int] = field(default_factory=list)
    property_name: str = ""           # which Z3 property triggered
    timestamp: float = 0.0
    code_hash: str = ""               # for deduplication

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "function_name": self.function_name,
            "is_buggy": self.is_buggy,
            "z3_label": self.z3_label,
            "gnn_confidence": self.gnn_confidence,
            "gnn_was_correct": self.gnn_was_correct,
            "bug_lines": self.bug_lines,
            "property_name": self.property_name,
            "timestamp": self.timestamp,
            "code_hash": self.code_hash,
        }

    @staticmethod
    def from_dict(d: dict) -> "Experience":
        return Experience(**{k: v for k, v in d.items() if k in Experience.__dataclass_fields__})


class ExperienceStore:
    """Persistent store for Z3-labeled code samples from real usage.

    Samples are stored as JSON files in ~/.sequent/experience/.
    Deduplication by code hash prevents the same function from
    being stored multiple times.
    """

    def __init__(self, store_dir: str = DEFAULT_EXPERIENCE_DIR):
        self.store_dir = store_dir
        os.makedirs(store_dir, exist_ok=True)
        self._index_path = os.path.join(store_dir, "index.json")
        self._index = self._load_index()

    def _load_index(self) -> dict:
        if os.path.exists(self._index_path):
            with open(self._index_path) as f:
                return json.load(f)
        return {"total_samples": 0, "since_last_learn": 0, "learn_count": 0,
                "hashes": [], "version": 1}

    def _save_index(self):
        with open(self._index_path, "w") as f:
            json.dump(self._index, f, indent=2)

    @staticmethod
    def _hash_code(code: str) -> str:
        return hashlib.sha256(code.strip().encode()).hexdigest()[:16]

    def save(self, exp: Experience):
        """Save an experience sample. Skips duplicates by code hash."""
        exp.code_hash = self._hash_code(exp.code)
        exp.timestamp = time.time()

        if exp.code_hash in self._index["hashes"]:
            return  # deduplicate

        # Save sample
        filename = f"{exp.code_hash}.json"
        filepath = os.path.join(self.store_dir, filename)
        with open(filepath, "w") as f:
            json.dump(exp.to_dict(), f, indent=2)

        self._index["hashes"].append(exp.code_hash)
        self._index["total_samples"] += 1
        self._index["since_last_learn"] += 1
        self._save_index()

    def load_all(self) -> list[Experience]:
        """Load all stored experiences."""
        samples = []
        for h in self._index["hashes"]:
            filepath = os.path.join(self.store_dir, f"{h}.json")
            if os.path.exists(filepath):
                with open(filepath) as f:
                    samples.append(Experience.from_dict(json.load(f)))
        return samples

    def get_stats(self) -> dict:
        """Get store statistics."""
        samples = self.load_all()
        if not samples:
            return {"total": 0, "buggy": 0, "clean": 0, "gnn_accuracy": 0.0,
                    "since_last_learn": 0, "learn_cycles": self._index["learn_count"]}

        buggy = sum(1 for s in samples if s.is_buggy)
        correct = sum(1 for s in samples if s.gnn_was_correct)
        return {
            "total": len(samples),
            "buggy": buggy,
            "clean": len(samples) - buggy,
            "gnn_accuracy": correct / len(samples) if samples else 0.0,
            "since_last_learn": self._index["since_last_learn"],
            "learn_cycles": self._index["learn_count"],
        }

    def mark_learned(self):
        """Mark that a learning cycle consumed current samples."""
        self._index["since_last_learn"] = 0
        self._index["learn_count"] += 1
        self._save_index()

    def should_learn(self, min_samples: int = 50) -> bool:
        """Check if enough new samples have accumulated for a learning cycle."""
        return self._index["since_last_learn"] >= min_samples

    def export_dataset(self) -> list[dict]:
        """Export experiences as training dataset format (compatible with train.py)."""
        samples = self.load_all()
        dataset = []
        for exp in samples:
            if exp.z3_label == 2:  # skip unknowns
                continue
            sample = {
                "id": exp.code_hash,
                "code": exp.code,
                "is_buggy": exp.is_buggy,
                "bug_line": exp.bug_lines[0] if exp.bug_lines else None,
                "bug_type": exp.property_name or "unknown",
                "z3_label": exp.z3_label,
            }
            dataset.append(sample)
        return dataset


class OnlineLearner:
    """Fine-tunes the GNN on accumulated experience without catastrophic forgetting.

    Strategy:
    - Mix experience replay (new samples) with a subset of original training data
    - Use lower learning rate than initial training (1/10th)
    - EWC-inspired: penalize large weight changes from the base model
    - Validate on held-out experience; rollback if performance degrades
    - Save model versions for rollback
    """

    def __init__(
        self,
        model_dir: str = DEFAULT_MODEL_DIR,
        checkpoint_path: Optional[str] = None,
        experience_store: Optional[ExperienceStore] = None,
    ):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)

        self.checkpoint_path = checkpoint_path
        self.experience_store = experience_store or ExperienceStore()

        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else
            "mps" if torch.backends.mps.is_available() else "cpu"
        )

    def fine_tune(
        self,
        epochs: int = 30,
        lr: float = 0.0001,
        ewc_lambda: float = 100.0,
        replay_ratio: float = 0.3,
        min_samples: int = 20,
    ) -> dict:
        """Fine-tune the GNN on accumulated experience.

        Args:
            epochs: Number of fine-tuning epochs
            lr: Learning rate (should be much lower than initial training)
            ewc_lambda: Elastic Weight Consolidation penalty strength
            replay_ratio: Fraction of original training data to mix in (anti-forgetting)
            min_samples: Minimum experience samples to proceed

        Returns:
            Dict with fine-tuning metrics
        """
        from model.ast_to_graph import code_to_graph
        from model.gnn import build_pyg_data
        from model.train import compute_metrics, focal_loss

        try:
            from torch_geometric.loader import DataLoader as PyGDataLoader
        except ImportError:
            return {"error": "torch_geometric not installed"}

        # Load experience
        dataset = self.experience_store.export_dataset()
        if len(dataset) < min_samples:
            return {"error": f"Not enough samples ({len(dataset)}/{min_samples})"}

        # Convert experience to graphs
        experience_graphs = []
        for sample in dataset:
            graph = code_to_graph(
                code=sample["code"],
                bug_line=sample.get("bug_line"),
                is_buggy=sample["is_buggy"],
            )
            if graph is not None:
                graph["z3_label"] = torch.tensor([sample["z3_label"]], dtype=torch.long)
                experience_graphs.append(build_pyg_data(graph))

        if len(experience_graphs) < min_samples:
            return {"error": f"Only {len(experience_graphs)} valid graphs from {len(dataset)} samples"}

        # Split experience: 80% train, 20% validation
        np.random.seed(42)
        indices = np.random.permutation(len(experience_graphs))
        split = int(0.8 * len(indices))
        train_exp = [experience_graphs[i] for i in indices[:split]]
        val_exp = [experience_graphs[i] for i in indices[split:]]

        # Load replay data from original training set (anti-forgetting)
        replay_data = []
        original_dataset_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "dataset", "generated", "train_z3.json"
        )
        if os.path.exists(original_dataset_path) and replay_ratio > 0:
            from model.ast_to_graph import load_dataset_as_graphs
            all_original = load_dataset_as_graphs(original_dataset_path)
            # Sample a fraction
            n_replay = max(int(len(all_original) * replay_ratio), len(train_exp))
            n_replay = min(n_replay, len(all_original))
            replay_indices = np.random.choice(len(all_original), n_replay, replace=False)
            replay_data = [build_pyg_data(all_original[i]) for i in replay_indices]

        # Combine experience + replay
        train_data = train_exp + replay_data
        np.random.shuffle(train_data)

        # Load model
        if not self.checkpoint_path or not os.path.exists(self.checkpoint_path):
            return {"error": f"Checkpoint not found: {self.checkpoint_path}"}

        checkpoint = torch.load(self.checkpoint_path, map_location=self.device, weights_only=True)
        config = checkpoint["config"]

        model = SequentGNN(
            in_channels=config["in_channels"],
            hidden_channels=config["hidden_channels"],
            num_heads=config["num_heads"],
            dropout=config["dropout"],
            num_edge_types=config.get("num_edge_types", 3),
            edge_embed_dim=config.get("edge_embed_dim", 16),
        ).to(self.device)
        model.load_state_dict(checkpoint["model_state_dict"])

        # Save base weights for EWC penalty
        base_params = {n: p.clone().detach() for n, p in model.named_parameters()}

        # Training setup
        optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
        train_loader = PyGDataLoader(train_data, batch_size=32, shuffle=True)
        val_loader = PyGDataLoader(val_exp, batch_size=32) if val_exp else None

        node_criterion = torch.nn.BCELoss(reduction="none")

        # Baseline validation score (before fine-tuning)
        baseline_metrics = None
        if val_loader:
            baseline_metrics = self._evaluate(model, val_loader)

        # Fine-tune
        best_val_f1 = baseline_metrics["f1"] if baseline_metrics else 0.0
        best_state = None
        history = []

        for epoch in range(1, epochs + 1):
            model.train()
            total_loss = 0
            all_preds, all_labels = [], []

            for batch in train_loader:
                batch = batch.to(self.device)
                optimizer.zero_grad()

                edge_type = batch.edge_type if hasattr(batch, "edge_type") else None
                graph_pred, node_pred, _, _ = model(
                    batch.x, batch.edge_index, batch.batch, edge_type=edge_type
                )

                # Graph-level focal loss
                graph_loss = focal_loss(graph_pred.view(-1), batch.y.float())

                # Node-level loss
                node_losses = node_criterion(node_pred.view(-1), batch.node_labels.float())
                weights = torch.where(batch.node_labels > 0, 10.0, 1.0)
                node_loss = (node_losses * weights).mean()

                # EWC penalty — penalize drifting from base weights
                ewc_penalty = 0.0
                if ewc_lambda > 0:
                    for name, param in model.named_parameters():
                        if name in base_params:
                            ewc_penalty += ((param - base_params[name]) ** 2).sum()
                    ewc_penalty = ewc_lambda * ewc_penalty

                loss = graph_loss + 0.5 * node_loss + ewc_penalty
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()

                total_loss += loss.item()
                all_preds.append(graph_pred.detach().cpu().view(-1))
                all_labels.append(batch.y.detach().cpu().float())

            all_preds = torch.cat(all_preds)
            all_labels = torch.cat(all_labels)
            train_metrics = compute_metrics(all_preds, all_labels)

            # Validation
            val_metrics = self._evaluate(model, val_loader) if val_loader else None

            epoch_info = {
                "epoch": epoch,
                "train_loss": total_loss / len(train_loader),
                "train_f1": train_metrics["f1"],
            }
            if val_metrics:
                epoch_info["val_f1"] = val_metrics["f1"]
                epoch_info["val_acc"] = val_metrics["accuracy"]

                if val_metrics["f1"] > best_val_f1:
                    best_val_f1 = val_metrics["f1"]
                    best_state = {k: v.clone() for k, v in model.state_dict().items()}

            history.append(epoch_info)

        # Save improved model (or rollback)
        result = {
            "epochs": epochs,
            "experience_samples": len(experience_graphs),
            "replay_samples": len(replay_data),
            "baseline_f1": baseline_metrics["f1"] if baseline_metrics else None,
            "final_f1": best_val_f1,
            "improved": best_state is not None and (
                baseline_metrics is None or best_val_f1 > baseline_metrics["f1"]
            ),
            "history": history,
        }

        if result["improved"] and best_state is not None:
            # Save previous model as backup
            backup_path = os.path.join(self.model_dir, "previous_model.pt")
            shutil.copy2(self.checkpoint_path, backup_path)

            # Save new model
            torch.save({
                "epoch": checkpoint.get("epoch", 0) + epochs,
                "model_state_dict": best_state,
                "config": config,
                "self_learn_cycle": self.experience_store.get_stats()["learn_cycles"] + 1,
                "experience_samples": len(experience_graphs),
                "fine_tuned_from": self.checkpoint_path,
            }, self.checkpoint_path)

            result["model_saved"] = self.checkpoint_path
            result["backup_saved"] = backup_path
        else:
            result["model_saved"] = None
            result["rollback_reason"] = "Fine-tuning did not improve validation F1"

        # Mark experience as consumed
        self.experience_store.mark_learned()

        # Save learning history
        history_path = os.path.join(self.model_dir, "self_learn_history.json")
        all_history = []
        if os.path.exists(history_path):
            with open(history_path) as f:
                all_history = json.load(f)
        all_history.append({
            "cycle": self.experience_store.get_stats()["learn_cycles"],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **result,
        })
        with open(history_path, "w") as f:
            json.dump(all_history, f, indent=2)

        return result

    @torch.no_grad()
    def _evaluate(self, model, loader) -> dict:
        """Evaluate model on a data loader."""
        from model.train import compute_metrics

        model.eval()
        all_preds, all_labels = [], []

        for batch in loader:
            batch = batch.to(self.device)
            edge_type = batch.edge_type if hasattr(batch, "edge_type") else None
            graph_pred, _, _, _ = model(batch.x, batch.edge_index, batch.batch, edge_type=edge_type)
            all_preds.append(graph_pred.cpu().view(-1))
            all_labels.append(batch.y.cpu().float())

        all_preds = torch.cat(all_preds)
        all_labels = torch.cat(all_labels)
        return compute_metrics(all_preds, all_labels)

    def rollback(self) -> bool:
        """Rollback to the previous model version."""
        backup_path = os.path.join(self.model_dir, "previous_model.pt")
        if not os.path.exists(backup_path):
            return False
        shutil.copy2(backup_path, self.checkpoint_path)
        return True


def collect_experience(result, experience_store: ExperienceStore):
    """Extract experience from a SequentResult and store it.

    Called automatically after each analyze() run when self-learning is enabled.

    Args:
        result: A SequentResult from the neurosymbolic pipeline
        experience_store: Where to save the experience
    """
    if result.verification is None:
        return

    z3_buggy = result.verification.has_bugs
    gnn_buggy = result.gnn_prediction.is_buggy if result.gnn_prediction else False
    gnn_conf = result.gnn_prediction.buggy_confidence if result.gnn_prediction else 0.0
    gnn_lines = result.gnn_prediction.bug_lines if result.gnn_prediction else []

    # Z3 label: 0=verified, 1=counterexample
    if result.verification.overall_result.value == "verified":
        z3_label = 0
    elif result.verification.overall_result.value == "counterexample":
        z3_label = 1
    else:
        z3_label = 2  # unknown — still store but won't be used for training

    # Which property triggered the bug?
    property_name = ""
    if result.verification.counterexamples:
        property_name = result.verification.counterexamples[0].property_name

    exp = Experience(
        code=result.code,
        function_name=result.function_name,
        is_buggy=z3_buggy,
        z3_label=z3_label,
        gnn_confidence=gnn_conf,
        gnn_was_correct=(gnn_buggy == z3_buggy),
        bug_lines=gnn_lines,
        property_name=property_name,
    )

    experience_store.save(exp)
