"""Tests for verifier/badges.py — SVG badge generation."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verifier.badges import (
    generate_badge,
    generate_summary_badge,
    badge_from_certificate,
    save_badge,
)


class TestGenerateBadge:

    def test_verified_badge(self):
        svg = generate_badge("add", "verified")
        assert "<svg" in svg
        assert "verified" in svg
        assert "add" in svg
        assert "sequent" in svg

    def test_buggy_badge(self):
        svg = generate_badge("divide", "buggy")
        assert "bug detected" in svg
        assert "divide" in svg

    def test_with_confidence(self):
        svg = generate_badge("foo", "buggy", confidence=0.92)
        assert "92%" in svg

    def test_with_time(self):
        svg = generate_badge("bar", "verified", time_ms=123.4)
        assert "123ms" in svg

    def test_warning_badge(self):
        svg = generate_badge("baz", "warning")
        assert "warning" in svg

    def test_unknown_badge(self):
        svg = generate_badge("unk", "unknown")
        assert "unknown" in svg

    def test_special_chars_escaped(self):
        svg = generate_badge("func<>&", "verified")
        assert "&lt;" in svg or "func" in svg  # HTML escaped


class TestGenerateSummaryBadge:

    def test_all_verified(self):
        svg = generate_summary_badge(verified=5, buggy=0)
        assert "5/5 verified" in svg
        assert "#22c55e" in svg  # green

    def test_some_buggy(self):
        svg = generate_summary_badge(verified=3, buggy=2)
        assert "2 bugs" in svg
        assert "3 verified" in svg
        assert "#f97316" in svg  # orange

    def test_single_bug(self):
        svg = generate_summary_badge(verified=1, buggy=1)
        assert "1 bug" in svg
        assert "1 verified" in svg

    def test_no_functions(self):
        svg = generate_summary_badge(verified=0, buggy=0)
        assert "no functions" in svg

    def test_with_time(self):
        svg = generate_summary_badge(verified=3, buggy=0, total_time_ms=456.7)
        assert "457ms" in svg


class TestBadgeFromCertificate:

    def test_from_cert_dict(self):
        cert = {
            "summary": {"verified": 4, "bugs_found": 1},
        }
        svg = badge_from_certificate(cert)
        assert "4 verified" in svg
        assert "1 bug" in svg


class TestSaveBadge:

    def test_save_to_file(self, tmp_path):
        svg = generate_summary_badge(verified=2, buggy=0)
        path = str(tmp_path / "badge.svg")
        save_badge(svg, path)

        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "<svg" in content
        assert "2/2 verified" in content
