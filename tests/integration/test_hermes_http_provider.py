from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from fastapi.testclient import TestClient

from api.app import app
from gods.config import runtime_config

client = TestClient(app)


class _EchoHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) if n > 0 else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = {}
        out = {"echo": body, "ok": True}
        data = json.dumps(out).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        return


def _start_http_server() -> tuple[HTTPServer, int]:
    srv = HTTPServer(("127.0.0.1", 0), _EchoHandler)
    port = srv.server_port
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, port


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


def test_hermes_http_provider_sync():
    project_id = "test_hermes_http_world"
    old_project = runtime_config.current_project
    srv, port = _start_http_server()
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)

        spec = {
            "name": "bridge.echo",
            "mode": "both",
            "provider": {
                "type": "http",
                "project_id": project_id,
                "url": f"http://127.0.0.1:{port}/echo",
                "method": "POST",
            },
            "request_schema": {
                "type": "object",
                "required": ["msg"],
                "properties": {"msg": {"type": "string"}},
            },
            "response_schema": {
                "type": "object",
                "required": ["result", "status_code"],
                "properties": {
                    "status_code": {"type": "integer"},
                    "result": {"type": "object"},
                },
            },
        }
        reg = client.post("/hermes/register", json={"project_id": project_id, "spec": spec})
        assert reg.status_code == 200

        inv = client.post(
            "/hermes/invoke",
            json={
                "project_id": project_id,
                "caller_id": "tester",
                "name": "bridge.echo",
                "mode": "sync",
                "payload": {"msg": "hello"},
            },
        )
        assert inv.status_code == 200
        data = inv.json()
        assert data.get("ok") is True
        assert data.get("result", {}).get("status_code") == 200
        assert data.get("result", {}).get("result", {}).get("echo", {}).get("msg") == "hello"
    finally:
        srv.shutdown()
        srv.server_close()
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
