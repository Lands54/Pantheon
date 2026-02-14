"""
Gods Communication MCP Server (stdio, JSON-RPC framing).

Bridges MCP tool calls to local Gods HTTP Tool Gateway endpoints.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import requests


SERVER_NAME = "gods-comm-mcp"
SERVER_VERSION = "0.1.0"


TOOLS = [
    {
        "name": "list_agents",
        "description": "List agents and role summaries in a project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "caller_id": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "check_inbox",
        "description": "Check an agent inbox from Gods buffer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "project_id": {"type": "string"},
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "send_message",
        "description": "Send a private message from one agent to another.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_id": {"type": "string"},
                "to_id": {"type": "string"},
                "message": {"type": "string"},
                "project_id": {"type": "string"},
            },
            "required": ["from_id", "to_id", "message"],
        },
    },
    {
        "name": "record_protocol",
        "description": "Record a protocol clause for knowledge graph extraction.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "topic": {"type": "string"},
                "relation": {"type": "string"},
                "object": {"type": "string"},
                "clause": {"type": "string"},
                "counterparty": {"type": "string"},
                "status": {"type": "string"},
                "project_id": {"type": "string"},
            },
            "required": ["subject", "topic", "relation", "object", "clause"],
        },
    },
]


def _send(msg: dict[str, Any]):
    data = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
    sys.stdout.buffer.write(header)
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def _read_message() -> dict[str, Any] | None:
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        try:
            key, value = line.decode("ascii").split(":", 1)
            headers[key.strip().lower()] = value.strip()
        except Exception:
            return None
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    body = sys.stdin.buffer.read(length)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _result(req_id: Any, payload: Any):
    _send({"jsonrpc": "2.0", "id": req_id, "result": payload})


def _error(req_id: Any, code: int, message: str):
    _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _tool_text(text: str, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _call_gateway(base_url: str, name: str, args: dict[str, Any]) -> str:
    if name == "list_agents":
        r = requests.get(f"{base_url}/tool-gateway/list_agents", params=args, timeout=20)
    elif name == "check_inbox":
        r = requests.post(f"{base_url}/tool-gateway/check_inbox", json=args, timeout=20)
    elif name == "send_message":
        r = requests.post(f"{base_url}/tool-gateway/send_message", json=args, timeout=20)
    elif name == "record_protocol":
        r = requests.post(f"{base_url}/tool-gateway/record_protocol", json=args, timeout=20)
    else:
        raise ValueError(f"Unknown tool: {name}")
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
    data = r.json()
    return json.dumps(data, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Gods communication MCP server")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    while True:
        req = _read_message()
        if req is None:
            break

        method = req.get("method")
        req_id = req.get("id")
        params = req.get("params", {}) or {}

        # Notifications (no id) can be ignored safely
        if req_id is None:
            continue

        try:
            if method == "initialize":
                _result(
                    req_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    },
                )
            elif method == "ping":
                _result(req_id, {})
            elif method == "tools/list":
                _result(req_id, {"tools": TOOLS})
            elif method == "tools/call":
                name = params.get("name", "")
                arguments = params.get("arguments", {}) or {}
                out = _call_gateway(args.base_url, name, arguments)
                _result(req_id, _tool_text(out, is_error=False))
            else:
                _error(req_id, -32601, f"Method not found: {method}")
        except Exception as e:
            _result(req_id, _tool_text(f"{type(e).__name__}: {e}", is_error=True))


if __name__ == "__main__":
    main()
