"""
Z3 Labeling Pass for Sequent.

Runs Z3 verification on every sample in the dataset and attaches a
z3_label field:
  0 = verified (Z3 proved all properties)
  1 = counterexample (Z3 found at least one counterexample)
  2 = unknown (Z3 couldn't decide / unsupported)

Samples labeled 'unknown' are excluded from contrastive loss during training.
"""

import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verifier.z3_engine import Z3Verifier, VerificationResult

Z3_VERIFIED = 0
Z3_COUNTEREXAMPLE = 1
Z3_UNKNOWN = 2


def label_sample(sample: dict, timeout_ms: int = 3000) -> int:
    """Run Z3 on a single sample and return the label."""
    verifier = Z3Verifier(timeout_ms=timeout_ms)
    try:
        report = verifier.verify(sample['code'], sample.get('function_name', ''))
        if report.overall_result == VerificationResult.VERIFIED:
            return Z3_VERIFIED
        elif report.overall_result == VerificationResult.COUNTEREXAMPLE:
            return Z3_COUNTEREXAMPLE
        else:
            return Z3_UNKNOWN
    except Exception:
        return Z3_UNKNOWN


def _label_worker(args):
    """Worker function for parallel labeling."""
    idx, sample, timeout_ms = args
    return idx, label_sample(sample, timeout_ms)


def label_dataset(input_path: str, output_path: str, timeout_ms: int = 3000, workers: int = 4):
    """Label an entire dataset JSON file with Z3 outcomes."""
    with open(input_path) as f:
        samples = json.load(f)

    print(f"Labeling {len(samples)} samples from {input_path}...")
    t0 = time.time()

    labels = [Z3_UNKNOWN] * len(samples)
    tasks = [(i, s, timeout_ms) for i, s in enumerate(samples)]

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_label_worker, t): t[0] for t in tasks}
        done = 0
        for future in as_completed(futures):
            idx, label = future.result()
            labels[idx] = label
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(samples)} done...")

    # Attach labels
    for sample, label in zip(samples, labels):
        sample['z3_label'] = label

    # Stats
    n_verified = sum(1 for l in labels if l == Z3_VERIFIED)
    n_counter = sum(1 for l in labels if l == Z3_COUNTEREXAMPLE)
    n_unknown = sum(1 for l in labels if l == Z3_UNKNOWN)
    elapsed = time.time() - t0

    print(f"  verified={n_verified}, counterexample={n_counter}, unknown={n_unknown}")
    print(f"  {elapsed:.1f}s total ({elapsed/len(samples)*1000:.1f}ms/sample)")

    with open(output_path, 'w') as f:
        json.dump(samples, f, indent=2)

    print(f"  Saved to {output_path}")
    return samples


def main():
    dataset_dir = os.path.join(os.path.dirname(__file__), 'generated')

    for split in ['train', 'val', 'test']:
        input_path = os.path.join(dataset_dir, f'{split}.json')
        output_path = os.path.join(dataset_dir, f'{split}_z3.json')
        if os.path.exists(input_path):
            label_dataset(input_path, output_path)


if __name__ == '__main__':
    main()
