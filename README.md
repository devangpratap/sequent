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

**Self-learning neurosymbolic code verifier.** 10M params. Runs offline. Free forever.

<p align="center">
  <img src="assets/demo.svg" alt="Sequent CLI demo" width="720"/>
</p>

Sequent proves your code correct — or finds the exact input that breaks it. A GATv2 graph neural network reads your code's structure, a Z3 SMT solver formally verifies it, and a consensus layer merges both verdicts. It learns from every run, getting sharper the more you use it.

**Python + JavaScript/TypeScript.** No API keys. No cloud. No cost.

## Install

```bash
pip install sequent-verify
```

## Usage

```bash
sequent check main.py                  # verify a file
sequent check main.py -f binary_search # verify one function
sequent check main.py --repair -v      # auto-fix bugs + re-verify
sequent check app.js                   # JS/TS support
sequent check main.py --cert proof.json # export formal proof certificate
sequent watch src/                     # re-verify on save
```

## How it works

```
Source Code → Code Property Graph → GATv2 GNN (10M params) → Bug predictions
                                  → Z3 SMT Solver           → Formal proofs
                                  → Consensus                → Verdict
                                  → Self-Learning            → Gets better
```

1. **GNN proposes** — reads the AST/CFG/data-flow graph and flags suspect nodes
2. **Z3 disposes** — formally verifies 8 property classes, produces counterexamples
3. **Consensus** — both must agree before a verdict is issued
4. **Self-learning** — verification outcomes feed back into GNN training data; accuracy improves with usage

## Benchmark (20 cases: 14 buggy, 6 clean)

| Tool | Bugs found | False positives | Accuracy | Cost | Proof |
|---|---|---|---|---|---|
| **Sequent** | **13/14 (92.9%)** | 2/6 | **85.0%** | Free | Z3 counterexample |
| Claude Sonnet 4 | 13/14 (92.9%) | 1/6 | 90.0% | ~$0.003/fn | None (natural language) |
| pylint | 0/14 | 0/6 | 30.0% | Free | None |
| pyflakes | 0/14 | 0/6 | 30.0% | Free | None |

Sequent matches Claude on bug recall (92.9%) while running **100x lighter**, fully offline, and free. Claude produces natural-language guesses; Sequent produces **Z3 counterexamples** — formal proofs that the bug exists. Static analyzers can't reason about semantics at all.

> 10M parameters vs 175B+. No API key. No internet. Gets better with every run.

<details>
<summary><strong>Full case-by-case breakdown</strong></summary>

| Category | Case | Bug | Sequent | Claude |
|---|---|---|---|---|
| Off-by-one | `binary_search_obo` | `<` vs `<=` | Detected | Detected |
| Off-by-one | `bubble_sort_obo` | Index OOB | Detected | Detected |
| None deref | `find_max_none` | No None check | Detected | Detected |
| None deref | `reverse_string_none` | No None check | Detected | Detected |
| None deref | `sum_list_none` | No None check | Missed | Detected |
| Div-by-zero | `average_no_guard` | Empty list | Detected | Detected |
| Div-by-zero | `normalize_no_guard` | Zero divisor | Detected | Detected |
| Wrong op | `is_even_wrong_op` | `==1` vs `==0` | Detected | Detected |
| Wrong op | `min_of_two_wrong` | Returns max | Detected | Detected |
| Unsafe arith | `factorial_no_guard` | Negative n | Detected | Missed |
| Boundary | `second_largest_no_check` | No len check | Detected | Detected |
| Boundary | `pop_empty` | No empty check | Detected | Detected |
| Mutation | `remove_dupes_mutate` | Mutate while iter | Detected | Detected |
| Logic | `swap_wrong` | Overwrite | Detected | Detected |
| Clean | `binary_search_correct` | — | OK | OK |
| Clean | `find_max_correct` | — | OK | OK |
| Clean | `safe_divide_correct` | — | OK | OK |
| Clean | `fibonacci_correct` | — | OK | OK |
| Clean | `is_palindrome_correct` | — | FP | OK |
| Clean | `gcd_correct` | — | FP | FP |

</details>

## Architecture

| Component | Detail |
|---|---|
| **Model** | GATv2, 8 heads, 256 hidden, 3 layers (~10M params) |
| **Graph** | Code Property Graph = AST + CFG + data flow |
| **Training** | Focal loss + NT-Xent contrastive, Z3 outcomes as supervision |
| **Dataset** | 14,144 synthetic mutations from 164 seed functions |
| **Self-learning** | Verification results auto-collected; periodic fine-tuning |
| **Metrics** | 85.0% acc, 86.7% prec, 92.9% recall, 89.7% F1 |

## Editor integration

Works with **any** editor via LSP — no extension marketplace needed.

```bash
sequent-lsp              # stdio
sequent-lsp --tcp --port 2087   # TCP
```

<details>
<summary>Neovim / Helix / Emacs / VS Code config</summary>

**Neovim**
```lua
vim.lsp.start({ name = "sequent", cmd = { "sequent-lsp" }, filetypes = { "python", "javascript", "typescript" } })
```

**Helix** (`~/.config/helix/languages.toml`)
```toml
[[language]]
name = "python"
language-servers = ["sequent-lsp"]
[language-server.sequent-lsp]
command = "sequent-lsp"
```

**Emacs**
```elisp
(lsp-register-client
  (make-lsp-client :new-connection (lsp-stdio-connection "sequent-lsp")
                   :major-modes '(python-mode js-mode typescript-mode)
                   :server-id 'sequent))
```

**VS Code / Cursor** — point any generic LSP client at `sequent-lsp`.
</details>

## License

MIT
