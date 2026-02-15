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


def test_cli_protocol_contract_commands(monkeypatch, capsys, tmp_path):
    calls = {"post": [], "get": []}

    def fake_get(url, params=None, timeout=0):
        calls["get"].append((url, params))
        if url.endswith("/config"):
            return _Resp(payload={"current_project": "default", "projects": {"default": {}}})
        if url.endswith("/hermes/contracts/list"):
            return _Resp(payload={"project_id": "default", "contracts": []})
        return _Resp(payload={})

    def fake_post(url, json=None, timeout=0):
        calls["post"].append((url, json))
        return _Resp(status_code=200, payload={"status": "success"})

    monkeypatch.setattr(protocol_cmd.requests, "get", fake_get)
    monkeypatch.setattr(protocol_cmd.requests, "post", fake_post)

    contract_file = tmp_path / "contract.json"
    contract_file.write_text('{"title":"c1","description":"d","version":"1.0.0","clauses":[]}', encoding="utf-8")

    args_register = SimpleNamespace(subcommand="contract-register", project=None, file=str(contract_file))
    protocol_cmd.cmd_protocol(args_register)

    args_list = SimpleNamespace(subcommand="contract-list", project=None, include_disabled=False)
    protocol_cmd.cmd_protocol(args_list)

    out = capsys.readouterr().out
    assert any("/hermes/contracts/register" in url for url, _ in calls["post"])
    assert any("/hermes/contracts/list" in url for url, _ in calls["get"])
