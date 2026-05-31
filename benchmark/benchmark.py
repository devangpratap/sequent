"""
Benchmark: Sequent vs Claude/GPT on bug detection.

Run after final model is trained:
    python3 benchmark/benchmark.py --run-all
    python3 benchmark/benchmark.py --sequent-only  (no API key needed)

Outputs comparison table + JSON results.
"""

import json
import os
import sys
import time
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark_cases import BENCHMARK_CASES
from verifier.neurosymbolic import SequentEngine


@dataclass
class BenchmarkResult:
    function_name: str
    ground_truth_buggy: bool
    bug_description: str
    sequent_detected: bool = False
    sequent_confidence: float = 0.0
    sequent_counterexample: str = ""
    sequent_time_ms: float = 0.0
    pylint_detected: bool = False
    pylint_issues: str = ""
    pyflakes_detected: bool = False
    pyflakes_issues: str = ""
    claude_detected: bool = False
    claude_response: str = ""
    claude_time_ms: float = 0.0


def run_sequent(engine: SequentEngine, cases: list) -> list[BenchmarkResult]:
    results = []
    for case in cases:
        t0 = time.time()
        r = engine.analyze(case["code"], case["name"])
        elapsed = (time.time() - t0) * 1000

        br = BenchmarkResult(
            function_name=case["name"],
            ground_truth_buggy=case["is_buggy"],
            bug_description=case["bug_description"],
            sequent_detected=r.consensus_buggy,
            sequent_confidence=r.gnn_prediction.buggy_confidence if r.gnn_prediction else 0,
            sequent_counterexample=r.verification.counterexamples[0].description if r.verification and r.verification.counterexamples else "",
            sequent_time_ms=elapsed,
        )
        results.append(br)
    return results


def run_static_analysis(cases: list, results: list[BenchmarkResult]):
    """Run pylint and pyflakes on each function."""
    import subprocess
    import tempfile

    for i, case in enumerate(cases):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(case["code"])
            tmp_path = f.name

        try:
            # Pylint
            try:
                out = subprocess.run(
                    ["python3", "-m", "pylint", tmp_path, "--disable=C,R",
                     "--output-format=text", "--score=no"],
                    capture_output=True, text=True, timeout=10
                )
                pylint_output = out.stdout.strip()
                # Pylint reports errors (E) and warnings (W)
                has_issues = any(f": E" in line or f": W" in line for line in pylint_output.splitlines())
                results[i].pylint_detected = has_issues
                results[i].pylint_issues = pylint_output[:200] if has_issues else ""
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            # Pyflakes
            try:
                out = subprocess.run(
                    ["python3", "-m", "pyflakes", tmp_path],
                    capture_output=True, text=True, timeout=10
                )
                pyflakes_output = out.stdout.strip()
                has_issues = len(pyflakes_output) > 0
                results[i].pyflakes_detected = has_issues
                results[i].pyflakes_issues = pyflakes_output[:200] if has_issues else ""
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        finally:
            os.unlink(tmp_path)


def run_claude(cases: list, results: list[BenchmarkResult]):
    """Call Claude API to check each function. Requires ANTHROPIC_API_KEY."""
    try:
        import anthropic
    except ImportError:
        print("anthropic package not installed — skipping Claude benchmark")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set — skipping Claude benchmark")
        return

    client = anthropic.Anthropic(api_key=api_key)

    for i, case in enumerate(cases):
        prompt = f"""Analyze this Python function for bugs. Reply with ONLY a JSON object:
{{"has_bug": true/false, "explanation": "brief explanation"}}

```python
{case["code"]}
```"""

        t0 = time.time()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = (time.time() - t0) * 1000

        text = response.content[0].text.strip()
        try:
            parsed = json.loads(text)
            results[i].claude_detected = parsed.get("has_bug", False)
            results[i].claude_response = parsed.get("explanation", "")
        except json.JSONDecodeError:
            results[i].claude_detected = "bug" in text.lower() or "error" in text.lower()
            results[i].claude_response = text[:200]

        results[i].claude_time_ms = elapsed


def _score(results, buggy_cases, clean_cases, detect_field):
    tp = sum(1 for r in buggy_cases if getattr(r, detect_field))
    fp = sum(1 for r in clean_cases if getattr(r, detect_field))
    fn = sum(1 for r in buggy_cases if not getattr(r, detect_field))
    tn = sum(1 for r in clean_cases if not getattr(r, detect_field))
    return tp, tn, fp, fn


def print_comparison(results: list[BenchmarkResult], include_claude: bool):
    total = len(results)
    buggy_cases = [r for r in results if r.ground_truth_buggy]
    clean_cases = [r for r in results if not r.ground_truth_buggy]

    print("\n" + "=" * 90)
    print("BENCHMARK RESULTS: Sequent vs Static Analysis")
    print("=" * 90)

    header = f"{'Function':<25} {'Truth':<7} {'Sequent':<9} {'Pylint':<9} {'Pyflakes':<9}"
    if include_claude:
        header += f" {'Claude':<9}"
    print(header)
    print("-" * 90)

    for r in results:
        def _mark(detected, truth):
            return "\033[92m✓\033[0m" if detected == truth else "\033[91m✗\033[0m"

        truth = 'BUG' if r.ground_truth_buggy else 'OK'
        line = f"{r.function_name:<25} {truth:<7} {_mark(r.sequent_detected, r.ground_truth_buggy)}        "
        line += f" {_mark(r.pylint_detected, r.ground_truth_buggy)}        "
        line += f" {_mark(r.pyflakes_detected, r.ground_truth_buggy)}        "
        if include_claude:
            line += f" {_mark(r.claude_detected, r.ground_truth_buggy)}        "
        print(line)

    print("-" * 90)

    for name, field in [("Sequent ", "sequent_detected"),
                        ("Pylint  ", "pylint_detected"),
                        ("Pyflakes", "pyflakes_detected")]:
        tp, tn, fp, fn = _score(results, buggy_cases, clean_cases, field)
        print(f"{name}: {tp + tn}/{total} correct  (TP={tp}, TN={tn}, FP={fp}, FN={fn})")

    if include_claude:
        tp, tn, fp, fn = _score(results, buggy_cases, clean_cases, "claude_detected")
        print(f"Claude  : {tp + tn}/{total} correct  (TP={tp}, TN={tn}, FP={fp}, FN={fn})")

    sequent_avg_ms = sum(r.sequent_time_ms for r in results) / total
    print(f"\nSequent avg latency: {sequent_avg_ms:.0f}ms")
    if include_claude:
        claude_avg_ms = sum(r.claude_time_ms for r in results) / total
        print(f"Claude avg latency: {claude_avg_ms:.0f}ms")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-all", action="store_true", help="Run both Sequent and Claude")
    parser.add_argument("--sequent-only", action="store_true", help="Run Sequent only")
    parser.add_argument("--output", default="benchmark/results.json", help="Output JSON path")
    args = parser.parse_args()

    model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "checkpoints", "best_model.pt")
    engine = SequentEngine(model_path=model_path)

    print("Running Sequent on benchmark cases...")
    results = run_sequent(engine, BENCHMARK_CASES)

    print("Running static analysis (pylint, pyflakes)...")
    run_static_analysis(BENCHMARK_CASES, results)

    include_claude = False
    if args.run_all:
        print("Running Claude on benchmark cases...")
        run_claude(BENCHMARK_CASES, results)
        include_claude = True

    print_comparison(results, include_claude)

    # Save results
    output = [
        {
            "function": r.function_name,
            "ground_truth": "buggy" if r.ground_truth_buggy else "clean",
            "bug_description": r.bug_description,
            "sequent_detected": r.sequent_detected,
            "sequent_confidence": round(r.sequent_confidence, 4),
            "sequent_counterexample": r.sequent_counterexample,
            "sequent_time_ms": round(r.sequent_time_ms, 1),
            "pylint_detected": r.pylint_detected,
            "pyflakes_detected": r.pyflakes_detected,
            "claude_detected": r.claude_detected,
            "claude_response": r.claude_response,
            "claude_time_ms": round(r.claude_time_ms, 1),
        }
        for r in results
    ]
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
