"""Vercel serverless endpoint: real Z3 verification (no GNN — PyTorch is too heavy for serverless).

Mirrors the FastAPI /analyze response shape so the existing Playground UI works unchanged.
The neural GNN panel and heatmap simply don't appear when `gnn` is null.
"""
import ast
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler

# Make the vendored `verifier` package importable regardless of CWD.
sys.path.insert(0, os.path.dirname(__file__))

from verifier.z3_engine import verify_code  # noqa: E402
from verifier.js_verifier import verify_js  # noqa: E402


def _looks_like_python(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _report_to_dict(report) -> dict:
    checks = [
        {
            "property_name": c.property_name,
            "result": c.result.value,
            "description": c.description,
            "line": c.line,
            "counterexample": c.counterexample,
            "time_ms": round(c.time_ms, 2),
        }
        for c in report.checks
    ]
    bugs = report.counterexamples
    is_buggy = report.has_bugs

    if is_buggy:
        consensus = f"Z3 found {len(bugs)} counterexample(s) — bug confirmed with a concrete input."
    elif report.is_verified:
        consensus = "Z3 formally verified every property — proven correct."
    else:
        consensus = "Z3 found no counterexamples (some properties were undecidable)."

    return {
        "function_name": report.function_name,
        "is_buggy": is_buggy,
        "consensus": consensus,
        "total_time_ms": round(report.total_time_ms, 1),
        "gnn": None,
        "z3": {
            "result": report.overall_result.value,
            "checks": checks,
            "bugs_found": len(bugs),
            "time_ms": round(report.total_time_ms, 1),
        },
        "repair": None,
    }


def _analyze(code: str, function_name: str = "") -> dict:
    start = time.time()
    if _looks_like_python(code):
        report = verify_code(code, function_name)
    else:
        report = verify_js(code, function_name)
    result = _report_to_dict(report)
    result["total_time_ms"] = round((time.time() - start) * 1000, 1)
    return result


class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw or b"{}")
            code = (data.get("code") or "").strip()
            if not code:
                self._send(400, {"error": "Code cannot be empty"})
                return
            result = _analyze(code, data.get("function_name", ""))
            self._send(200, result)
        except Exception as exc:  # noqa: BLE001 — surface a clean message to the UI
            self._send(500, {"error": f"Verification failed: {exc}"})

    def do_GET(self):
        self._send(200, {"status": "ok", "engine": "z3-only", "note": "POST code to verify"})
