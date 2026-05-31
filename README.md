```
                           _
 ___ ___ __ _ _  _ ___ _ _| |_
(_-</ -_) _` | || / -_) ' \  _|
/__/\___\__, |\_,_\___|_||_\__|
           |_|
```

**Neural Formal Verification Engine** — GNN proposes, Z3 disposes.

Sequent is a neurosymbolic Python debugger that **proves your code correct** — or finds the exact counterexample that breaks it.

## How it works

```
Python Source → AST Parser → GATv2 (10M params) → Bug Predictions
                          → Z3 SMT Solver       → Formal Proofs
                          → Consensus Vote       → Verdict + Counterexample
                          → Auto-Repair          → Re-Verify
```

1. **GNN proposes**: A GATv2 graph neural network reads your Python AST and predicts which nodes are likely bugs
2. **Z3 disposes**: The Z3 SMT solver formally verifies 8 property classes against your code
3. **Consensus**: Neural predictions are merged with formal proofs — both must agree
4. **Auto-repair**: If a bug is found, Sequent generates a fix and re-verifies it through Z3

## Install

```bash
pip install sequent
```

## Usage

```bash
# Verify a file
sequent check main.py

# Verify a specific function
sequent check main.py -f binary_search

# Auto-repair detected bugs
sequent check main.py --repair -v

# Export proof certificate
sequent check main.py --cert report.json

# JSON output for CI
sequent check main.py --json
```

## Example

```bash
$ sequent check test_buggy.py

  binary_search  ✗ BUG DETECTED  (42ms)
  ────────────────────────────────────────────────────────
  GNN  Buggy (87.3%)  12ms
       ⚑ Suspect lines: [4]
  Z3   ✗ counterexample  28ms
       ✗ loop_invariant: Loop uses '<' instead of '<=': misses case when low == high
         ↳ counterexample: {"low": "n", "high": "n"}
  ────────────────────────────────────────────────────────
  Consensus: BUG CONFIRMED: GNN detected bug and Z3 produced a formal counterexample.

  safe_divide  ✓ VERIFIED  (18ms)
  ────────────────────────────────────────────────────────
  Consensus: VERIFIED: Both GNN and Z3 agree — no bugs detected.
```

## Supported bug classes

| Bug Type | Description |
|----------|-------------|
| `off_by_one` | Loop bounds off by 1 (`<` vs `<=`) |
| `boundary_error` | Array/index out of bounds |
| `wrong_operator` | Incorrect comparison/arithmetic operators |
| `none_deref` | Missing null/None checks |
| `integer_overflow` | Unchecked arithmetic overflow |
| `missing_return` | Missing return in code path |
| `wrong_init` | Incorrect variable initialization |

## Z3 property checks

- Comparison consistency (off-by-one in loops)
- Array index bounds (upper and lower)
- None/null safety
- Return completeness
- Division by zero / arithmetic safety
- Loop termination and invariants
- Dead code detection

## Architecture

- **Model**: GATv2 with 8 attention heads, 256 hidden channels, 3 layers (~10M params)
- **Graph**: Code Property Graph (CPG) = AST + CFG + data flow
- **Features**: 91 AST node types + structural features (depth, subtree size, loop/conditional context)
- **Edges**: Parent↔child (AST) + control flow (CFG) + data flow (def → use)
- **Training**: Focal loss + NT-Xent contrastive loss with Z3 verification outcomes as supervision
- **Dataset**: 14,144 synthetic mutations from 164 seed functions, seed-level train/test split
- **Metrics**: 74.0% accuracy, 83.0% precision, 73.6% recall, 78.0% F1

## Web playground

```bash
# Start the API server
pip install sequent[server]
python -m backend.server

# Start the frontend (development)
cd frontend && npm install && npm run dev
```

## GitHub Action

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.11'
- run: pip install sequent
- run: sequent check src/ --ci --cert sequent-report.json
```

## License

MIT
