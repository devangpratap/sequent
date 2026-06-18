"""Tests for lsp_server.py — LSP protocol and verification."""

import io
import json
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lsp_server import SequentLSPServer, _read_message, _write_message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_message(msg: dict) -> bytes:
    """Encode a JSON-RPC message with Content-Length framing."""
    body = json.dumps(msg).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
    return header + body


def _send_and_receive(server, request: dict) -> dict | None:
    """Send a request to the server and read the response."""
    input_data = _make_message(request)
    input_stream = io.BytesIO(input_data)
    output_stream = io.BytesIO()

    class OutputWrapper:
        def __init__(self, buf):
            self.buffer = buf
        def write(self, data):
            self.buffer.write(data if isinstance(data, bytes) else data.encode())
        def flush(self):
            pass

    server.input = input_stream
    server.output = OutputWrapper(output_stream)

    msg = _read_message(input_stream)
    if msg:
        server._handle(msg)

    output_stream.seek(0)
    response = _read_message(output_stream)
    return response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLSPProtocol:

    def test_read_write_message(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "test"}
        buf = io.BytesIO()

        class Wrapper:
            def __init__(self, b):
                self.buffer = b
            def write(self, data):
                self.buffer.write(data if isinstance(data, bytes) else data.encode())
            def flush(self):
                pass

        _write_message(Wrapper(buf), msg)
        buf.seek(0)
        result = _read_message(buf)

        assert result["id"] == 1
        assert result["method"] == "test"

    def test_initialize(self):
        server = SequentLSPServer()
        response = _send_and_receive(server, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"capabilities": {}},
        })

        assert response is not None
        assert response["id"] == 1
        result = response["result"]
        assert "capabilities" in result
        assert result["capabilities"]["hoverProvider"] is True
        assert result["serverInfo"]["name"] == "sequent-lsp"

    def test_shutdown(self):
        server = SequentLSPServer()
        # Initialize first
        _send_and_receive(server, {
            "jsonrpc": "2.0", "id": 1,
            "method": "initialize", "params": {},
        })

        response = _send_and_receive(server, {
            "jsonrpc": "2.0", "id": 2,
            "method": "shutdown", "params": {},
        })

        assert response is not None
        assert server.running is False

    def test_unknown_method(self):
        server = SequentLSPServer()
        response = _send_and_receive(server, {
            "jsonrpc": "2.0", "id": 99,
            "method": "nonexistent/method", "params": {},
        })

        assert response is not None
        assert "error" in response
        assert response["error"]["code"] == -32601


class TestLSPDocumentSync:

    def test_did_open(self):
        server = SequentLSPServer()
        server._on_did_open({
            "textDocument": {
                "uri": "file:///test.py",
                "languageId": "python",
                "text": "def foo(): pass",
            },
        }, None)

        assert "file:///test.py" in server.documents
        assert server.documents["file:///test.py"] == "def foo(): pass"

    def test_did_change(self):
        server = SequentLSPServer()
        server.documents["file:///test.py"] = "old"

        server._on_did_change({
            "textDocument": {"uri": "file:///test.py"},
            "contentChanges": [{"text": "new content"}],
        }, None)

        assert server.documents["file:///test.py"] == "new content"

    def test_did_close(self):
        server = SequentLSPServer()
        server.documents["file:///test.py"] = "code"
        server.diagnostics_cache["file:///test.py"] = []

        # Capture the notification
        notifications = []
        original_notify = server._notify
        server._notify = lambda m, p: notifications.append((m, p))

        server._on_did_close({
            "textDocument": {"uri": "file:///test.py"},
        }, None)

        assert "file:///test.py" not in server.documents
        assert "file:///test.py" not in server.diagnostics_cache
        assert len(notifications) == 1
        assert notifications[0][0] == "textDocument/publishDiagnostics"


class TestLSPHover:

    def test_hover_on_function_def(self):
        server = SequentLSPServer()
        uri = "file:///test.py"
        server.documents[uri] = "def add(a, b):\n    return a + b"
        server.diagnostics_cache[uri] = [{
            "name": "add",
            "verdict": "verified",
            "consensus": "VERIFIED",
            "time_ms": 42.0,
            "gnn": {"prediction": "clean", "confidence": 0.3, "suspect_lines": []},
            "z3": {"result": "verified", "properties_checked": 12, "properties_verified": 12,
                   "counterexamples": []},
        }]

        result = server._on_hover({
            "textDocument": {"uri": uri},
            "position": {"line": 0, "character": 5},
        }, 1)

        assert result is not None
        assert "Verified" in result["contents"]["value"]

    def test_hover_not_on_def(self):
        server = SequentLSPServer()
        uri = "file:///test.py"
        server.documents[uri] = "x = 1\ndef add(a, b):\n    return a + b"

        result = server._on_hover({
            "textDocument": {"uri": uri},
            "position": {"line": 0, "character": 0},
        }, 1)

        assert result is None


class TestLSPCodeAction:

    def test_code_action_with_repair(self):
        server = SequentLSPServer()
        uri = "file:///test.py"
        server.documents[uri] = "def divide(a, b):\n    return a / b\n"
        server.diagnostics_cache[uri] = [{
            "name": "divide",
            "verdict": "buggy",
            "consensus": "BUG",
            "time_ms": 50.0,
            "repair": {
                "description": "Added zero-division guard",
                "verified": True,
                "repaired_code": "def divide(a, b):\n    if b == 0:\n        return None\n    return a / b",
            },
        }]

        actions = server._on_code_action({
            "textDocument": {"uri": uri},
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 10}},
            "context": {
                "diagnostics": [{
                    "source": "sequent",
                    "code": "divide",
                    "message": "BUG",
                    "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 10}},
                }],
            },
        }, 1)

        assert len(actions) == 1
        assert "zero-division" in actions[0]["title"]
        assert actions[0]["isPreferred"] is True
        assert "edit" in actions[0]

    def test_code_action_no_repair(self):
        server = SequentLSPServer()
        uri = "file:///test.py"
        server.documents[uri] = "def foo(): pass"
        server.diagnostics_cache[uri] = [{
            "name": "foo",
            "verdict": "buggy",
            "consensus": "BUG",
            "time_ms": 10.0,
        }]

        actions = server._on_code_action({
            "textDocument": {"uri": uri},
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 5}},
            "context": {
                "diagnostics": [{
                    "source": "sequent",
                    "code": "foo",
                    "message": "BUG",
                    "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 5}},
                }],
            },
        }, 1)

        assert actions == []


class TestLSPVerification:

    def test_extract_functions(self):
        server = SequentLSPServer()
        source = "def a():\n    pass\n\ndef b():\n    return 1\n"
        funcs = server._extract_functions(source)

        assert len(funcs) == 2
        assert funcs[0][0] == "a"
        assert funcs[1][0] == "b"
        assert funcs[0][2] == 0  # start line
        assert funcs[1][2] == 3

    def test_find_function_range(self):
        server = SequentLSPServer()
        source = "x = 1\n\ndef foo():\n    return 42\n\ndef bar():\n    pass\n"

        result = server._find_function_range(source, "foo")
        assert result == (2, 3)

        result = server._find_function_range(source, "bar")
        assert result == (5, 6)

        result = server._find_function_range(source, "nonexistent")
        assert result is None
