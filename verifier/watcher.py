"""
Incremental Analysis + File Watcher for Sequent.

Watches Python files for changes and re-analyzes only the functions
that actually changed, using AST-level diffing for precision.

Usage:
    sequent watch .                     # Watch current directory
    sequent watch src/ tests/           # Watch specific directories
    sequent watch file.py               # Watch a single file
"""

from __future__ import annotations

import ast
import hashlib
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class FunctionSnapshot:
    """Snapshot of a function for change detection."""
    name: str
    source: str
    source_hash: str
    start_line: int
    end_line: int


@dataclass
class FileSnapshot:
    """Snapshot of a Python file's function ASTs."""
    path: str
    mtime: float
    functions: dict[str, FunctionSnapshot] = field(default_factory=dict)


class IncrementalAnalyzer:
    """Tracks function-level changes and only re-analyzes what changed."""

    def __init__(self):
        self.snapshots: dict[str, FileSnapshot] = {}  # path -> FileSnapshot
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            from verifier.neurosymbolic import SequentEngine
            model_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "checkpoints", "best_model.pt",
            )
            if not os.path.exists(model_path):
                model_path = None
            self._engine = SequentEngine(model_path=model_path, self_learn=True)
        return self._engine

    @staticmethod
    def _hash_source(source: str) -> str:
        return hashlib.sha256(source.strip().encode()).hexdigest()[:16]

    @staticmethod
    def _extract_functions(source: str) -> dict[str, FunctionSnapshot]:
        """Extract function snapshots from Python source."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {}

        lines = source.split("\n")
        functions = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                start = node.lineno - 1
                end = node.end_lineno
                func_source = "\n".join(lines[start:end])
                functions[node.name] = FunctionSnapshot(
                    name=node.name,
                    source=func_source,
                    source_hash=IncrementalAnalyzer._hash_source(func_source),
                    start_line=start + 1,
                    end_line=end,
                )
        return functions

    def get_changed_functions(self, filepath: str) -> tuple[list[str], list[str], list[str]]:
        """Compare file against snapshot and return (added, modified, removed) function names."""
        try:
            with open(filepath) as f:
                source = f.read()
        except (OSError, UnicodeDecodeError):
            return [], [], []

        new_functions = self._extract_functions(source)
        old_snapshot = self.snapshots.get(filepath)

        if old_snapshot is None:
            return list(new_functions.keys()), [], []

        old_funcs = old_snapshot.functions
        added = [n for n in new_functions if n not in old_funcs]
        removed = [n for n in old_funcs if n not in new_functions]
        modified = [
            n for n in new_functions
            if n in old_funcs and new_functions[n].source_hash != old_funcs[n].source_hash
        ]

        return added, modified, removed

    def update_snapshot(self, filepath: str):
        """Update the stored snapshot for a file."""
        try:
            with open(filepath) as f:
                source = f.read()
            mtime = os.path.getmtime(filepath)
        except (OSError, UnicodeDecodeError):
            return

        functions = self._extract_functions(source)
        self.snapshots[filepath] = FileSnapshot(
            path=filepath,
            mtime=mtime,
            functions=functions,
        )

    def analyze_changed(self, filepath: str) -> list[dict]:
        """Analyze only changed functions in a file. Returns list of result summaries."""
        added, modified, removed = self.get_changed_functions(filepath)
        changed = added + modified

        if not changed:
            self.update_snapshot(filepath)
            return []

        try:
            with open(filepath) as f:
                source = f.read()
        except (OSError, UnicodeDecodeError):
            return []

        new_functions = self._extract_functions(source)
        results = []

        for name in changed:
            func_snap = new_functions.get(name)
            if not func_snap:
                continue

            result = self.engine.analyze(func_snap.source, name)
            results.append({
                "function": name,
                "change_type": "added" if name in added else "modified",
                "verdict": "buggy" if result.consensus_buggy else "verified",
                "description": result.consensus_description,
                "time_ms": result.total_time_ms,
                "line": func_snap.start_line,
            })

        self.update_snapshot(filepath)
        return results


class FileWatcher:
    """Poll-based file watcher that triggers incremental analysis on changes."""

    def __init__(
        self,
        paths: list[str],
        analyzer: Optional[IncrementalAnalyzer] = None,
        poll_interval: float = 1.0,
        on_result=None,
    ):
        self.paths = paths
        self.analyzer = analyzer or IncrementalAnalyzer()
        self.poll_interval = poll_interval
        self.on_result = on_result
        self.running = False

        # Track file modification times
        self._mtimes: dict[str, float] = {}

    def _collect_py_files(self) -> list[str]:
        """Collect all .py files from the watched paths."""
        files = []
        for p in self.paths:
            if os.path.isfile(p) and p.endswith(".py"):
                files.append(os.path.abspath(p))
            elif os.path.isdir(p):
                for root, dirs, filenames in os.walk(p):
                    # Skip common non-source dirs
                    dirs[:] = [
                        d for d in dirs
                        if d not in {"__pycache__", ".git", "node_modules", ".venv", "venv", ".tox", "dist", "build"}
                    ]
                    for fn in filenames:
                        if fn.endswith(".py"):
                            files.append(os.path.join(root, fn))
        return files

    def _check_changes(self) -> list[str]:
        """Return list of files that changed since last check."""
        changed = []
        current_files = set(self._collect_py_files())

        for filepath in current_files:
            try:
                mtime = os.path.getmtime(filepath)
            except OSError:
                continue

            old_mtime = self._mtimes.get(filepath)
            if old_mtime is None or mtime > old_mtime:
                changed.append(filepath)
                self._mtimes[filepath] = mtime

        # Remove deleted files
        for filepath in list(self._mtimes.keys()):
            if filepath not in current_files:
                del self._mtimes[filepath]
                self.analyzer.snapshots.pop(filepath, None)

        return changed

    def watch(self):
        """Start the watch loop (blocking)."""
        self.running = True

        # Initial scan — build snapshots without analyzing
        for filepath in self._collect_py_files():
            try:
                self._mtimes[filepath] = os.path.getmtime(filepath)
                self.analyzer.update_snapshot(filepath)
            except OSError:
                pass

        while self.running:
            try:
                changed = self._check_changes()
                for filepath in changed:
                    results = self.analyzer.analyze_changed(filepath)
                    if results and self.on_result:
                        self.on_result(filepath, results)
                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                self.running = False

    def stop(self):
        self.running = False


# ---------------------------------------------------------------------------
# CLI output callback
# ---------------------------------------------------------------------------

def _cli_on_result(filepath: str, results: list[dict]):
    """Pretty-print watch results to terminal."""
    # Terminal colors
    RESET = "\033[0m"
    PURPLE = "\033[38;5;135m"
    PURPLE_DIM = "\033[38;5;97m"
    ORANGE = "\033[38;5;208m"
    GREEN = "\033[92m"
    GRAY = "\033[90m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"

    rel_path = os.path.relpath(filepath)
    timestamp = time.strftime("%H:%M:%S")

    print(f"\n  {PURPLE_DIM}[{timestamp}]{RESET} {WHITE}{rel_path}{RESET}")

    for r in results:
        change_tag = f"{GRAY}({r['change_type']}){RESET}"
        if r["verdict"] == "buggy":
            icon = f"{ORANGE}\u2717{RESET}"
            verdict = f"{ORANGE}BUG DETECTED{RESET}"
        else:
            icon = f"{GREEN}\u2713{RESET}"
            verdict = f"{GREEN}VERIFIED{RESET}"

        print(f"    {icon} {BOLD}{r['function']}{RESET}  {verdict}  "
              f"{GRAY}L{r['line']} {r['time_ms']:.0f}ms{RESET} {change_tag}")

        if r["verdict"] == "buggy":
            desc = r.get("description", "")
            if desc:
                # Truncate long descriptions
                if len(desc) > 100:
                    desc = desc[:97] + "..."
                print(f"      {PURPLE_DIM}{desc}{RESET}")
