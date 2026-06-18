"""
Proof Certificate Badge Generator for Sequent.

Generates SVG badges (like shields.io) for verification results.
Embed in READMEs, CI dashboards, or export alongside proof certificates.

Usage:
    from verifier.badges import generate_badge, generate_summary_badge
    svg = generate_badge("divide", "buggy", confidence=0.92)
    svg = generate_summary_badge(verified=5, buggy=1, total_time_ms=340)
"""

from __future__ import annotations

import html
from typing import Optional


# ---------------------------------------------------------------------------
# Color palette (matches Sequent terminal theme)
# ---------------------------------------------------------------------------

COLORS = {
    "verified": "#22c55e",      # green
    "buggy": "#f97316",         # orange
    "warning": "#eab308",       # yellow
    "unknown": "#6b7280",       # gray
    "label_bg": "#1e1b2e",      # deep purple (Sequent brand)
    "label_text": "#e2e0ea",    # light purple text
}


# ---------------------------------------------------------------------------
# SVG templates
# ---------------------------------------------------------------------------

_BADGE_TEMPLATE = """\
<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{aria_label}">
  <title>{aria_label}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="{label_bg}"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{value_bg}"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="11">
    <text aria-hidden="true" x="{label_x}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_x}" y="14" fill="{label_text}">{label}</text>
    <text aria-hidden="true" x="{value_x}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="{value_x}" y="14" fill="#fff">{value}</text>
  </g>
</svg>"""


def _text_width(text: str) -> int:
    """Estimate text width in pixels (approximate, matches shields.io heuristic)."""
    # Average character width ~6.5px at font-size 11
    return int(len(text) * 6.5) + 10


def generate_badge(
    function_name: str,
    verdict: str,
    confidence: Optional[float] = None,
    time_ms: Optional[float] = None,
) -> str:
    """Generate an SVG badge for a single function verification result.

    Args:
        function_name: Name of the verified function
        verdict: "verified", "buggy", "warning", or "unknown"
        confidence: Optional GNN confidence (0-1)
        time_ms: Optional verification time in ms

    Returns:
        SVG string
    """
    label = html.escape(f"sequent | {function_name}")
    verdict_lower = verdict.lower()

    # Build value text
    if verdict_lower == "verified":
        value = "verified"
        icon = "\u2713"  # ✓
    elif verdict_lower == "buggy":
        value = "bug detected"
        icon = "\u2717"  # ✗
    elif verdict_lower == "warning":
        value = "warning"
        icon = "!"
    else:
        value = "unknown"
        icon = "?"

    if confidence is not None:
        value += f" ({confidence:.0%})"
    if time_ms is not None:
        value += f" {time_ms:.0f}ms"

    value_display = f"{icon} {value}"
    value_bg = COLORS.get(verdict_lower, COLORS["unknown"])

    label_width = _text_width(label)
    value_width = _text_width(value_display)
    total_width = label_width + value_width

    return _BADGE_TEMPLATE.format(
        total_width=total_width,
        label_width=label_width,
        value_width=value_width,
        label_x=label_width // 2,
        value_x=label_width + value_width // 2,
        label=label,
        value=html.escape(value_display),
        label_bg=COLORS["label_bg"],
        label_text=COLORS["label_text"],
        value_bg=value_bg,
        aria_label=html.escape(f"sequent {function_name}: {verdict}"),
    )


def generate_summary_badge(
    verified: int = 0,
    buggy: int = 0,
    total_time_ms: Optional[float] = None,
) -> str:
    """Generate an SVG summary badge for a whole file/project.

    Args:
        verified: Number of verified functions
        buggy: Number of buggy functions
        total_time_ms: Optional total verification time

    Returns:
        SVG string
    """
    total = verified + buggy
    label = "sequent"

    if buggy == 0 and verified > 0:
        value = f"\u2713 {verified}/{total} verified"
        value_bg = COLORS["verified"]
    elif buggy > 0:
        value = f"\u2717 {buggy} bug{'s' if buggy > 1 else ''} | {verified} verified"
        value_bg = COLORS["buggy"]
    else:
        value = "no functions"
        value_bg = COLORS["unknown"]

    if total_time_ms is not None:
        value += f" ({total_time_ms:.0f}ms)"

    label_width = _text_width(label)
    value_width = _text_width(value)
    total_width = label_width + value_width

    return _BADGE_TEMPLATE.format(
        total_width=total_width,
        label_width=label_width,
        value_width=value_width,
        label_x=label_width // 2,
        value_x=label_width + value_width // 2,
        label=label,
        value=html.escape(value),
        label_bg=COLORS["label_bg"],
        label_text=COLORS["label_text"],
        value_bg=value_bg,
        aria_label=html.escape(f"sequent: {verified} verified, {buggy} bugs"),
    )


def badge_from_certificate(cert: dict) -> str:
    """Generate a summary badge from a proof certificate dict."""
    summary = cert.get("summary", {})
    return generate_summary_badge(
        verified=summary.get("verified", 0),
        buggy=summary.get("bugs_found", 0),
    )


def save_badge(svg: str, path: str):
    """Save an SVG badge to a file."""
    with open(path, "w") as f:
        f.write(svg)
