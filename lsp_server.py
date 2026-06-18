"""
Sequent LSP Server — Language Server Protocol for any editor.

Provides real-time verification diagnostics, hover info, and code actions
via the standard LSP protocol. Works with any LSP-compatible editor
(Neovim, Emacs, Sublime Text, Helix, etc.).

Usage:
    python -m sequent.lsp          # stdio mode (default)
    python -m sequent.lsp --tcp    # TCP mode on port 2087
"""

import ast
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# JSON-RPC / LSP base protocol
# ---------------------------------------------------------------------------

def _read_message(stream) -> Optional[dict]:
    """Read a JSON-RPC message from an LSP stream (Content-Length framing)."""
    headers = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        line = line.decode("utf-8") if isinstance(line, bytes) else line
        line = line.strip()
        if not line:
            break
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()

    content_length = int(headers.get("Content-Length", 0))
    if content_length == 0:
        return None

    body = stream.read(content_length)
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    return json.loads(body)


def _write_message(stream, msg: dict):
    """Write a JSON-RPC message to an LSP stream."""
    body = json.dumps(msg)
    header = f"Content-Length: {len(body)}\r\n\r\n"
    data = header + body
    if hasattr(stream, "buffer"):
        stream.buffer.write(data.encode("utf-8"))
        stream.buffer.flush()
    else:
        stream.write(data.encode("utf-8"))
        stream.flush()


# ---------------------------------------------------------------------------
# LSP Server
# ---------------------------------------------------------------------------

class SequentLSPServer:
    """Minimal LSP server implementing the Sequent verification pipeline."""

    def __init__(self, input_stream=None, output_stream=None):
        self.input = input_stream or sys.stdin.buffer
        self.output = output_stream or sys.stdout
        self.running = False
        self.initialized = False
        self.executor = ThreadPoolExecutor(max_workers=2)

        # Document state
        self.documents: dict[str, str] = {}  # uri -> content
        self.diagnostics_cache: dict[str, list] = {}  # uri -> cert functions

        # Engine (lazy-loaded)
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            from verifier.neurosymbolic import SequentEngine
            model_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "checkpoints", "best_model.pt",
            )
            if not os.path.exists(model_path):
                model_path = None
            self._engine = SequentEngine(model_path=model_path, self_learn=True)
        return self._engine

    # --- Main loop ---------------------------------------------------------

    def serve(self):
        """Run the LSP server main loop (stdio)."""
        self.running = True
        while self.running:
            msg = _read_message(self.input)
            if msg is None:
                break
            self._handle(msg)

    def _send(self, msg: dict):
        msg["jsonrpc"] = "2.0"
        _write_message(self.output, msg)

    def _respond(self, request_id, result):
        self._send({"id": request_id, "result": result})

    def _respond_error(self, request_id, code: int, message: str):
        self._send({"id": request_id, "error": {"code": code, "message": message}})

    def _notify(self, method: str, params: dict):
        self._send({"method": method, "params": params})

    # --- Message dispatch --------------------------------------------------

    def _handle(self, msg: dict):
        method = msg.get("method", "")
        params = msg.get("params", {})
        request_id = msg.get("id")

        handler = {
            "initialize": self._on_initialize,
            "initialized": self._on_initialized,
            "shutdown": self._on_shutdown,
            "exit": self._on_exit,
            "textDocument/didOpen": self._on_did_open,
            "textDocument/didChange": self._on_did_change,
            "textDocument/didSave": self._on_did_save,
            "textDocument/didClose": self._on_did_close,
            "textDocument/hover": self._on_hover,
            "textDocument/codeAction": self._on_code_action,
        }.get(method)

        _NO_RESPONSE = object()

        if handler:
            result = handler(params, request_id)
            if request_id is not None and result is not _NO_RESPONSE:
                self._respond(request_id, result)
        elif request_id is not None:
            # Unknown request — respond with method not found
            self._respond_error(request_id, -32601, f"Method not found: {method}")

    # --- Lifecycle ---------------------------------------------------------

    def _on_initialize(self, params, request_id):
        self.initialized = True
        return {
            "capabilities": {
                "textDocumentSync": {
                    "openClose": True,
                    "change": 1,  # Full sync
                    "save": {"includeText": True},
                },
                "hoverProvider": True,
                "codeActionProvider": {
                    "codeActionKinds": ["quickfix"],
                },
                "diagnosticProvider": {
                    "interFileDependencies": False,
                    "workspaceDiagnostics": False,
                },
            },
            "serverInfo": {
                "name": "sequent-lsp",
                "version": "0.2.0",
            },
        }

    def _on_initialized(self, params, request_id):
        return None

    def _on_shutdown(self, params, request_id):
        self.running = False
        return None

    def _on_exit(self, params, request_id):
        self.running = False
        sys.exit(0)

    # --- Document sync -----------------------------------------------------

    def _on_did_open(self, params, request_id):
        td = params.get("textDocument", {})
        uri = td.get("uri", "")
        text = td.get("text", "")
        lang = td.get("languageId", "")

        self.documents[uri] = text
        if lang == "python":
            self.executor.submit(self._verify_and_publish, uri, text)
        return None

    def _on_did_change(self, params, request_id):
        td = params.get("textDocument", {})
        uri = td.get("uri", "")
        changes = params.get("contentChanges", [])
        if changes:
            self.documents[uri] = changes[-1].get("text", "")
        return None

    def _on_did_save(self, params, request_id):
        td = params.get("textDocument", {})
        uri = td.get("uri", "")
        text = params.get("text") or self.documents.get(uri, "")
        if text:
            self.documents[uri] = text
        self.executor.submit(self._verify_and_publish, uri, self.documents.get(uri, ""))
        return None

    def _on_did_close(self, params, request_id):
        td = params.get("textDocument", {})
        uri = td.get("uri", "")
        self.documents.pop(uri, None)
        self.diagnostics_cache.pop(uri, None)
        # Clear diagnostics
        self._notify("textDocument/publishDiagnostics", {
            "uri": uri,
            "diagnostics": [],
        })
        return None

    # --- Hover -------------------------------------------------------------

    def _on_hover(self, params, request_id):
        td = params.get("textDocument", {})
        uri = td.get("uri", "")
        pos = params.get("position", {})
        line = pos.get("line", 0)

        text = self.documents.get(uri, "")
        if not text:
            return None

        lines = text.split("\n")
        if line >= len(lines):
            return None

        # Check if cursor is on a function def line
        import re
        match = re.match(r"^\s*def\s+(\w+)\s*\(", lines[line])
        if not match:
            return None

        func_name = match.group(1)
        cached = self.diagnostics_cache.get(uri, [])
        func_info = next((f for f in cached if f.get("name") == func_name), None)
        if not func_info:
            return None

        # Build markdown hover
        parts = []
        verdict = func_info.get("verdict", "unknown")
        if verdict == "verified":
            parts.append("**Sequent: Verified**")
        else:
            parts.append("**Sequent: Bug Detected**")
            parts.append(f"\n{func_info.get('consensus', '')}")

        gnn = func_info.get("gnn")
        if gnn:
            pct = f"{gnn['confidence'] * 100:.1f}%"
            parts.append(f"\n**GNN:** {gnn['prediction']} ({pct} confidence)")
            if gnn.get("suspect_lines"):
                parts.append(f"Suspect lines: {gnn['suspect_lines']}")

        z3 = func_info.get("z3")
        if z3:
            parts.append(f"\n**Z3:** {z3['result']} ({z3['properties_checked']} properties, "
                         f"{z3['properties_verified']} verified)")
            for cx in z3.get("counterexamples", []):
                parts.append(f"\n`{cx['property']}`: {cx['description']}")

        parts.append(f"\n*{func_info.get('time_ms', 0):.0f}ms*")

        return {
            "contents": {
                "kind": "markdown",
                "value": "\n".join(parts),
            },
        }

    # --- Code actions ------------------------------------------------------

    def _on_code_action(self, params, request_id):
        td = params.get("textDocument", {})
        uri = td.get("uri", "")
        context = params.get("context", {})
        diagnostics = context.get("diagnostics", [])

        actions = []
        cached = self.diagnostics_cache.get(uri, [])

        for diag in diagnostics:
            if diag.get("source") != "sequent":
                continue

            func_name = diag.get("code", "")
            func_info = next((f for f in cached if f.get("name") == func_name), None)
            if not func_info:
                continue

            repair = func_info.get("repair")
            if not repair or not repair.get("repaired_code"):
                continue

            # Find function range in document
            text = self.documents.get(uri, "")
            func_range = self._find_function_range(text, func_name)
            if not func_range:
                continue

            start_line, end_line = func_range
            lines = text.split("\n")
            end_col = len(lines[end_line]) if end_line < len(lines) else 0

            verified_tag = " (verified)" if repair.get("verified") else " (unverified)"
            title = f"Sequent: Apply fix — {repair['description']}{verified_tag}"

            action = {
                "title": title,
                "kind": "quickfix",
                "diagnostics": [diag],
                "isPreferred": repair.get("verified", False),
                "edit": {
                    "changes": {
                        uri: [{
                            "range": {
                                "start": {"line": start_line, "character": 0},
                                "end": {"line": end_line, "character": end_col},
                            },
                            "newText": repair["repaired_code"],
                        }],
                    },
                },
            }
            actions.append(action)

        return actions

    # --- Verification pipeline --------------------------------------------

    def _verify_and_publish(self, uri: str, text: str):
        """Run verification and publish diagnostics (called on background thread)."""
        if not text.strip():
            self._notify("textDocument/publishDiagnostics", {
                "uri": uri, "diagnostics": [],
            })
            return

        try:
            functions = self._extract_functions(text)
        except SyntaxError:
            return

        if not functions:
            self._notify("textDocument/publishDiagnostics", {
                "uri": uri, "diagnostics": [],
            })
            return

        diagnostics = []
        cert_functions = []

        for name, func_source, start_line in functions:
            try:
                result = self.engine.analyze(func_source, name)
            except Exception:
                continue

            # Build cert-style dict for caching (hover/code actions)
            from verifier.z3_engine import VerificationResult
            func_cert = {
                "name": name,
                "verdict": "buggy" if result.consensus_buggy else "verified",
                "consensus": result.consensus_description,
                "time_ms": result.total_time_ms,
            }

            if result.gnn_prediction:
                func_cert["gnn"] = {
                    "prediction": "buggy" if result.gnn_prediction.is_buggy else "clean",
                    "confidence": result.gnn_prediction.buggy_confidence,
                    "suspect_lines": result.gnn_prediction.bug_lines,
                }

            if result.verification:
                func_cert["z3"] = {
                    "result": result.verification.overall_result.value,
                    "properties_checked": len(result.verification.checks),
                    "properties_verified": sum(
                        1 for c in result.verification.checks
                        if c.result == VerificationResult.VERIFIED
                    ),
                    "counterexamples": [
                        {
                            "property": c.property_name,
                            "description": c.description,
                            "line": c.line,
                            "counterexample": c.counterexample,
                        }
                        for c in result.verification.counterexamples
                    ],
                }

            if result.repair:
                func_cert["repair"] = {
                    "description": result.repair.repair_description,
                    "verified": result.repair.verified,
                    "repaired_code": result.repair.repaired_code,
                }

            cert_functions.append(func_cert)

            if not result.consensus_buggy:
                continue

            # Find best line for diagnostic
            diag_line = start_line
            if result.verification and result.verification.counterexamples:
                cx = result.verification.counterexamples[0]
                if cx.line and cx.line > 0:
                    diag_line = start_line + cx.line - 1
            elif result.gnn_prediction and result.gnn_prediction.bug_lines:
                diag_line = start_line + result.gnn_prediction.bug_lines[0] - 1

            diag = {
                "range": {
                    "start": {"line": diag_line, "character": 0},
                    "end": {"line": diag_line, "character": 200},
                },
                "severity": 1,  # Error
                "source": "sequent",
                "code": name,
                "message": f"Sequent: {result.consensus_description}",
            }

            # Related info from counterexamples
            if result.verification and result.verification.counterexamples:
                related = []
                for cx in result.verification.counterexamples:
                    cx_line = start_line + (cx.line - 1 if cx.line else 0)
                    related.append({
                        "location": {
                            "uri": uri,
                            "range": {
                                "start": {"line": cx_line, "character": 0},
                                "end": {"line": cx_line, "character": 0},
                            },
                        },
                        "message": f"{cx.property_name}: {cx.description}",
                    })
                diag["relatedInformation"] = related

            diagnostics.append(diag)

        self.diagnostics_cache[uri] = cert_functions

        self._notify("textDocument/publishDiagnostics", {
            "uri": uri,
            "diagnostics": diagnostics,
        })

    def _extract_functions(self, source: str) -> list[tuple[str, str, int]]:
        """Extract (name, source, start_line_0indexed) from Python source."""
        tree = ast.parse(source)
        functions = []
        lines = source.split("\n")
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                start = node.lineno - 1
                end = node.end_lineno
                func_source = "\n".join(lines[start:end])
                functions.append((node.name, func_source, start))
        return functions

    def _find_function_range(self, source: str, func_name: str) -> Optional[tuple[int, int]]:
        """Find (start_line, end_line) 0-indexed for a function."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return (node.lineno - 1, node.end_lineno - 1)
        return None


# ---------------------------------------------------------------------------
# TCP wrapper
# ---------------------------------------------------------------------------

def serve_tcp(host: str = "127.0.0.1", port: int = 2087):
    """Run the LSP server over TCP."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(1)
    print(f"Sequent LSP server listening on {host}:{port}", file=sys.stderr)

    while True:
        conn, addr = sock.accept()
        print(f"LSP client connected from {addr}", file=sys.stderr)
        rfile = conn.makefile("rb")
        wfile = conn.makefile("wb")

        class WriteWrapper:
            """Wrap socket file to match stdout interface."""
            def __init__(self, f):
                self.buffer = f
            def write(self, data):
                self.buffer.write(data if isinstance(data, bytes) else data.encode())
            def flush(self):
                self.buffer.flush()

        server = SequentLSPServer(input_stream=rfile, output_stream=WriteWrapper(wfile))
        try:
            server.serve()
        except Exception as e:
            print(f"LSP session error: {e}", file=sys.stderr)
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Sequent LSP Server")
    parser.add_argument("--tcp", action="store_true", help="Run in TCP mode")
    parser.add_argument("--port", type=int, default=2087, help="TCP port (default: 2087)")
    parser.add_argument("--host", default="127.0.0.1", help="TCP host (default: 127.0.0.1)")
    args = parser.parse_args()

    if args.tcp:
        serve_tcp(host=args.host, port=args.port)
    else:
        server = SequentLSPServer()
        server.serve()


if __name__ == "__main__":
    main()
