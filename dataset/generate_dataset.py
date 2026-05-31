"""
Dataset generator for Sequent.

Takes seed functions, applies all mutation types, and outputs:
- Correct samples (label=0, no bug location)
- Buggy samples (label=1, bug location marked)

IMPORTANT:
- Splits by SEED FUNCTION, not by sample — forces genuine generalization
- Balances buggy vs clean samples ~50/50 using correct variants
"""

import json
import os
import random
import textwrap
from pathlib import Path

from seed_functions import SEED_FUNCTIONS
from seed_functions_extra import EXTRA_SEED_FUNCTIONS
from mutation_engine import generate_all_mutations, BugType
from correct_variants import generate_correct_variants

ALL_SEEDS = SEED_FUNCTIONS + EXTRA_SEED_FUNCTIONS


def generate_dataset(output_dir: str = "generated", samples_per_seed: int = 10):
    os.makedirs(output_dir, exist_ok=True)

    stats = {bt.value: 0 for bt in BugType}
    stats["correct"] = 0

    # Group all samples by seed function
    seed_groups = {}  # seed_name → list of samples

    for seed in ALL_SEEDS:
        code = textwrap.dedent(seed["code"]).strip()
        name = seed["name"]
        category = seed["category"]

        buggy_samples = []
        clean_samples = []

        # Add the correct version
        clean_samples.append({
            "id": f"{name}_correct",
            "function_name": name,
            "category": category,
            "code": code,
            "is_buggy": False,
            "bug_type": None,
            "bug_line": None,
            "description": "Original correct implementation",
        })

        # Generate mutated (buggy) versions
        for attempt in range(samples_per_seed):
            mutations = generate_all_mutations(code, name)
            for mut in mutations:
                sample_id = f"{name}_{mut.bug_type.value}_{attempt}"
                buggy_samples.append({
                    "id": sample_id,
                    "function_name": name,
                    "category": category,
                    "code": mut.mutated_code,
                    "is_buggy": True,
                    "bug_type": mut.bug_type.value,
                    "bug_line": mut.bug_line,
                    "description": mut.description,
                    "original_code": mut.original_code,
                })
                stats[mut.bug_type.value] += 1

        # Generate correct variants to balance with buggy count
        num_buggy = len(buggy_samples)
        num_clean_needed = max(num_buggy - 1, 0)  # -1 for the original
        variants = generate_correct_variants(code, num_clean_needed)
        for vi, variant in enumerate(variants):
            clean_samples.append({
                "id": f"{name}_clean_variant_{vi}",
                "function_name": name,
                "category": category,
                "code": variant,
                "is_buggy": False,
                "bug_type": None,
                "bug_line": None,
                "description": f"Correct variant {vi}",
            })

        stats["correct"] += len(clean_samples)
        seed_groups[name] = buggy_samples + clean_samples

    # Split by SEED FUNCTION: 70/15/15
    seed_names = list(seed_groups.keys())
    random.seed(42)
    random.shuffle(seed_names)

    n_seeds = len(seed_names)
    train_end = int(0.70 * n_seeds)
    val_end = int(0.85 * n_seeds)

    train_seeds = seed_names[:train_end]
    val_seeds = seed_names[train_end:val_end]
    test_seeds = seed_names[val_end:]

    print(f"Seed split: {len(train_seeds)} train / {len(val_seeds)} val / {len(test_seeds)} test")

    # Build splits
    splits = {"train": [], "val": [], "test": []}
    for name in train_seeds:
        splits["train"].extend(seed_groups[name])
    for name in val_seeds:
        splits["val"].extend(seed_groups[name])
    for name in test_seeds:
        splits["test"].extend(seed_groups[name])

    # Shuffle within each split
    for split_data in splits.values():
        random.shuffle(split_data)

    for split_name, split_data in splits.items():
        path = os.path.join(output_dir, f"{split_name}.json")
        with open(path, "w") as f:
            json.dump(split_data, f, indent=2)
        buggy_count = sum(1 for s in split_data if s["is_buggy"])
        clean_count = sum(1 for s in split_data if not s["is_buggy"])
        ratio = buggy_count / max(clean_count, 1)
        print(f"  {split_name}: {len(split_data)} samples ({buggy_count} buggy, {clean_count} clean, ratio {ratio:.1f}:1) → {path}")

    total = sum(len(v) for v in splits.values())
    print(f"\nTotal: {total} samples")
    print(f"Stats: {stats}")

    # Also save full dataset
    full = splits["train"] + splits["val"] + splits["test"]
    with open(os.path.join(output_dir, "full_dataset.json"), "w") as f:
        json.dump(full, f, indent=2)

    return splits


if __name__ == "__main__":
    print("Generating Sequent dataset (seed-level split, balanced)...")
    generate_dataset()
