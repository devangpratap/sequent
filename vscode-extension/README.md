# Sequent - Neural Formal Verification for VS Code

Sequent brings neurosymbolic Python verification directly into your editor. A GNN trained on code property graphs proposes potential bugs, then Z3 confirms or refutes each finding with formal proofs. Diagnostics appear as squiggly underlines with hover details, and verified auto-repairs are offered as Quick Fix code actions.

## Install

**From VSIX (local build):**

```bash
cd vscode-extension
npm install && npm run compile
npx @vscode/vsce package
code --install-extension sequent-verify-0.1.0.vsix
```

**From Marketplace:** Search for "Sequent" in the VS Code Extensions panel (once published).

## Configuration

| Setting              | Type    | Default   | Description                                      |
|----------------------|---------|-----------|--------------------------------------------------|
| `sequent.pythonPath` | string  | `python3` | Path to the Python interpreter used to run Sequent |
| `sequent.autoVerify` | boolean | `true`    | Automatically run verification on save           |
| `sequent.severity`   | enum    | `Error`   | Diagnostic severity for detected bugs (`Error`, `Warning`, `Information`, `Hint`) |

## Commands

- **Sequent: Verify Current File** -- Run verification on the active Python file.
- **Sequent: Verify Function at Cursor** -- Verify only the function under the cursor.
- **Sequent: Apply Auto-Repair Suggestion** -- Apply a Sequent-generated fix for a detected bug.

## Requirements

- Python 3.9+
- `sequent` package installed (`pip install sequent-verify`)
- PyTorch and Z3 solver (installed as sequent dependencies)
