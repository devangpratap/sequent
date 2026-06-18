"""Tests for verifier/watcher.py — incremental analysis and file watching."""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verifier.watcher import IncrementalAnalyzer, FileWatcher


CLEAN_CODE = """\
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
"""

MODIFIED_CODE = """\
def add(a, b):
    return a + b + 1

def multiply(a, b):
    return a * b
"""

NEW_FUNC_CODE = """\
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b

def subtract(a, b):
    return a - b
"""

REMOVED_FUNC_CODE = """\
def add(a, b):
    return a + b
"""


class TestIncrementalAnalyzer:

    def test_first_scan_all_added(self, tmp_path):
        filepath = str(tmp_path / "test.py")
        with open(filepath, "w") as f:
            f.write(CLEAN_CODE)

        analyzer = IncrementalAnalyzer()
        added, modified, removed = analyzer.get_changed_functions(filepath)

        assert set(added) == {"add", "multiply"}
        assert modified == []
        assert removed == []

    def test_no_changes(self, tmp_path):
        filepath = str(tmp_path / "test.py")
        with open(filepath, "w") as f:
            f.write(CLEAN_CODE)

        analyzer = IncrementalAnalyzer()
        analyzer.update_snapshot(filepath)

        added, modified, removed = analyzer.get_changed_functions(filepath)
        assert added == []
        assert modified == []
        assert removed == []

    def test_detect_modification(self, tmp_path):
        filepath = str(tmp_path / "test.py")
        with open(filepath, "w") as f:
            f.write(CLEAN_CODE)

        analyzer = IncrementalAnalyzer()
        analyzer.update_snapshot(filepath)

        with open(filepath, "w") as f:
            f.write(MODIFIED_CODE)

        added, modified, removed = analyzer.get_changed_functions(filepath)
        assert added == []
        assert modified == ["add"]
        assert removed == []

    def test_detect_new_function(self, tmp_path):
        filepath = str(tmp_path / "test.py")
        with open(filepath, "w") as f:
            f.write(CLEAN_CODE)

        analyzer = IncrementalAnalyzer()
        analyzer.update_snapshot(filepath)

        with open(filepath, "w") as f:
            f.write(NEW_FUNC_CODE)

        added, modified, removed = analyzer.get_changed_functions(filepath)
        assert added == ["subtract"]
        assert modified == []
        assert removed == []

    def test_detect_removed_function(self, tmp_path):
        filepath = str(tmp_path / "test.py")
        with open(filepath, "w") as f:
            f.write(CLEAN_CODE)

        analyzer = IncrementalAnalyzer()
        analyzer.update_snapshot(filepath)

        with open(filepath, "w") as f:
            f.write(REMOVED_FUNC_CODE)

        added, modified, removed = analyzer.get_changed_functions(filepath)
        assert added == []
        assert modified == []
        assert removed == ["multiply"]

    def test_syntax_error_returns_empty(self, tmp_path):
        filepath = str(tmp_path / "bad.py")
        with open(filepath, "w") as f:
            f.write("def broken(:\n  pass")

        analyzer = IncrementalAnalyzer()
        added, modified, removed = analyzer.get_changed_functions(filepath)
        assert added == []
        assert modified == []
        assert removed == []

    def test_analyze_changed_returns_results(self, tmp_path):
        filepath = str(tmp_path / "test.py")
        with open(filepath, "w") as f:
            f.write(CLEAN_CODE)

        analyzer = IncrementalAnalyzer()
        results = analyzer.analyze_changed(filepath)

        # First run: all functions are "added"
        assert len(results) == 2
        names = {r["function"] for r in results}
        assert names == {"add", "multiply"}
        for r in results:
            assert r["change_type"] == "added"
            assert r["verdict"] in ("verified", "buggy")
            assert r["time_ms"] > 0

    def test_analyze_changed_skips_unchanged(self, tmp_path):
        filepath = str(tmp_path / "test.py")
        with open(filepath, "w") as f:
            f.write(CLEAN_CODE)

        analyzer = IncrementalAnalyzer()
        analyzer.analyze_changed(filepath)  # initial scan

        # No changes — should return empty
        results = analyzer.analyze_changed(filepath)
        assert results == []

    def test_analyze_changed_only_modified(self, tmp_path):
        filepath = str(tmp_path / "test.py")
        with open(filepath, "w") as f:
            f.write(CLEAN_CODE)

        analyzer = IncrementalAnalyzer()
        analyzer.analyze_changed(filepath)  # initial scan

        with open(filepath, "w") as f:
            f.write(MODIFIED_CODE)

        results = analyzer.analyze_changed(filepath)
        assert len(results) == 1
        assert results[0]["function"] == "add"
        assert results[0]["change_type"] == "modified"


class TestFileWatcher:

    def test_collect_py_files(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.txt").write_text("not python")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.py").write_text("y = 2")

        watcher = FileWatcher(paths=[str(tmp_path)])
        files = watcher._collect_py_files()

        py_files = {os.path.basename(f) for f in files}
        assert "a.py" in py_files
        assert "c.py" in py_files
        assert "b.txt" not in py_files

    def test_check_changes_new_file(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1")

        watcher = FileWatcher(paths=[str(tmp_path)])
        changed = watcher._check_changes()
        assert len(changed) == 1

        # No changes on second check
        changed = watcher._check_changes()
        assert len(changed) == 0

    def test_check_changes_modified_file(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x = 1")

        watcher = FileWatcher(paths=[str(tmp_path)])
        watcher._check_changes()  # initial

        time.sleep(0.05)
        f.write_text("x = 2")

        changed = watcher._check_changes()
        assert len(changed) == 1

    def test_skips_pycache(self, tmp_path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "cached.py").write_text("z = 1")
        (tmp_path / "real.py").write_text("x = 1")

        watcher = FileWatcher(paths=[str(tmp_path)])
        files = watcher._collect_py_files()
        names = {os.path.basename(f) for f in files}
        assert "real.py" in names
        assert "cached.py" not in names
