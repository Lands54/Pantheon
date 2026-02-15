from __future__ import annotations

from types import SimpleNamespace

from cli.commands import protocol as protocol_cmd


class _Resp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_cli_protocol_register_and_list(monkeypatch, capsys):
    calls = {"post": [], "get": []}

    def fake_get(url, params=None, timeout=0):
        calls["get"].append((url, params))
        if url.endswith("/config"):
            return _Resp(payload={"current_project": "default", "projects": {"default": {"hermes_allow_agent_tool_provider": True}}})
        if url.endswith("/hermes/list"):
            return _Resp(payload={"project_id": "default", "protocols": []})
        return _Resp(payload={})

    def fake_post(url, json=None, timeout=0):
        calls["post"].append((url, json))
        return _Resp(status_code=200, payload={"status": "success"})

    monkeypatch.setattr(protocol_cmd.requests, "get", fake_get)
    monkeypatch.setattr(protocol_cmd.requests, "post", fake_post)

    args_reg = SimpleNamespace(
        subcommand="register",
        project=None,
        name="alpha.list",
        description="",
        mode="both",
        provider="agent_tool",
        owner_agent="alpha",
        function_id="list_dir",
        agent="alpha",
        tool="list_dir",
        url=None,
        method="POST",
        request_schema='{"type":"object"}',
        response_schema='{"type":"object","required":["result"],"properties":{"result":{"type":"string"}}}',
        max_concurrency=2,
        rate_per_minute=60,
        timeout=30,
    )
    protocol_cmd.cmd_protocol(args_reg)

    args_list = SimpleNamespace(subcommand="list", project=None)
    protocol_cmd.cmd_protocol(args_list)

    out = capsys.readouterr().out
    assert "Protocol registered" in out
    assert any("/hermes/register" in url for url, _ in calls["post"])
    assert any("/hermes/list" in url for url, _ in calls["get"])
