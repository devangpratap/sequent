```
                           _
 ___ ___ __ _ _  _ ___ _ _| |_
(_-</ -_) _` | || / -_) ' \  _|
/__/\___\__, |\_,_\___|_||_\__|
           |_|
```

[![CI](https://github.com/devangpratap/sequent/actions/workflows/ci.yml/badge.svg)](https://github.com/devangpratap/sequent/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/sequent-verify)](https://pypi.org/project/sequent-verify/)
[![Python](https://img.shields.io/pypi/pyversions/sequent-verify)](https://pypi.org/project/sequent-verify/)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](https://opensource.org/licenses/MIT)

**Neural Formal Verification Engine** — GNN proposes, Z3 disposes.

Sequent is a neurosymbolic code verifier for **Python and JavaScript/TypeScript** that **proves your code correct** — or finds the exact counterexample that breaks it.

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
pip install sequent-verify
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

# Verify JavaScript/TypeScript
sequent check app.js
sequent check utils.ts -f calculateTotal

# Watch mode (re-verify on save)
sequent watch src/

# Generate verification badge
sequent badge main.py -o badge.svg

# Start LSP server (for Neovim, Emacs, Helix, etc.)
sequent lsp
sequent lsp --tcp --port 2087
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

## Benchmark

Sequent vs pylint vs pyflakes on 20 hand-crafted cases (14 buggy, 6 clean). Static analyzers
focus on style and syntax — they cannot reason about semantics, so they miss every logic bug.

| Bug Category | Case | Bug | Sequent | pylint | pyflakes |
|---|---|---|---|---|---|
| Off-by-one | `binary_search_obo` | `<` vs `<=` in loop | Detected | Missed | Missed |
| Off-by-one | `bubble_sort_obo` | Index out of bounds | Detected | Missed | Missed |
| None deref | `find_max_none` | No None check | Detected | Missed | Missed |
| None deref | `reverse_string_none` | No None check | Detected | Missed | Missed |
| None deref | `sum_list_none` | No None check | Missed | Missed | Missed |
| Div-by-zero | `average_no_guard` | Empty list division | Detected | Missed | Missed |
| Div-by-zero | `normalize_no_guard` | Zero divisor | Detected | Missed | Missed |
| Wrong operator | `is_even_wrong_op` | `== 1` vs `== 0` | Detected | Missed | Missed |
| Wrong operator | `min_of_two_wrong` | Returns max | Detected | Missed | Missed |
| Unsafe arith | `factorial_no_guard` | Negative n silent | Detected | Missed | Missed |
| Boundary | `second_largest_no_check` | No length check | Detected | Missed | Missed |
| Boundary | `pop_empty` | No empty check | Detected | Missed | Missed |
| Mutation | `remove_dupes_mutate` | Mutate while iterating | Detected | Missed | Missed |
| Logic | `swap_wrong` | Overwrite before save | Missed | Missed | Missed |
| Clean | `binary_search_correct` | — | FP | OK | OK |
| Clean | `find_max_correct` | — | FP | OK | OK |
| Clean | `safe_divide_correct` | — | OK | OK | OK |
| Clean | `fibonacci_correct` | — | OK | OK | OK |
| Clean | `is_palindrome_correct` | — | FP | OK | OK |
| Clean | `gcd_correct` | — | FP | OK | OK |

**Summary (20 cases)**

| Tool | Correct | Bugs found (of 14) | False positives (of 6) | Accuracy |
|---|---|---|---|---|
| **Sequent** | **14/20** | **12/14 (85.7%)** | 4/6 | **70.0%** |
| pylint | 6/20 | 0/14 (0%) | 0/6 | 30.0% |
| pyflakes | 6/20 | 0/14 (0%) | 0/6 | 30.0% |

Sequent catches semantic bugs (off-by-one, division by zero, wrong operators, missing guards)
that pylint and pyflakes are structurally blind to. The tradeoff is a higher false-positive rate
on clean code — Sequent's Z3 verifier is conservative and flags potential edge cases even in
correct implementations. Average Sequent latency: **230ms** per function.

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

## Git Hook

Sequent can verify staged Python files automatically before every commit.

**Manual install** (copies hook into `.git/hooks/`):

```bash
bash hooks/install.sh              # install
bash hooks/install.sh --uninstall  # remove
```

**pre-commit framework** ([pre-commit.com](https://pre-commit.com)):

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/devangpratapsingh/sequent
    rev: main
    hooks:
      - id: sequent-verify
```

The hook skips files over 10 KB for speed. To bypass on a single commit, use `git commit --no-verify`.

## LSP Server

Sequent ships an LSP server for editor-agnostic verification. Works with any LSP client.

**Neovim** (via `lspconfig`):

```lua
vim.lsp.start({
  name = "sequent",
  cmd = { "sequent-lsp" },
  filetypes = { "python", "javascript", "typescript" },
})
```

**Helix** (`~/.config/helix/languages.toml`):

```toml
[[language]]
name = "python"
language-servers = ["sequent-lsp"]

[language-server.sequent-lsp]
command = "sequent-lsp"
```

**Emacs** (via `lsp-mode`):

```elisp
(lsp-register-client
  (make-lsp-client :new-connection (lsp-stdio-connection "sequent-lsp")
                   :major-modes '(python-mode js-mode typescript-mode)
                   :server-id 'sequent))
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
