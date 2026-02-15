from argparse import Namespace

from fastapi.testclient import TestClient

from api.server import app
from cli.commands.runtime import cmd_runtime


client = TestClient(app)


class _Resp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def test_runtime_cli_status_and_reconcile(monkeypatch, capsys):
    project_id = "it_runtime_cli"

    client.post("/projects/create", json={"id": project_id})
    client.post("/agents/create", json={"agent_id": "ground", "directives": "# ground"})

    def _get(url, params=None, timeout=0):
        if url.endswith("/config"):
            cfg = client.get("/config").json()
            cfg["current_project"] = project_id
            client.post("/config/save", json=cfg)
            return _Resp(client.get("/config").json())
        path = url.replace("http://localhost:8000", "")
        return _Resp(client.get(path, params=params).json())

    def _post(url, json=None, timeout=0):
        path = url.replace("http://localhost:8000", "")
        return _Resp(client.post(path, json=json).json())

    monkeypatch.setattr("cli.commands.runtime.requests.get", _get)
    monkeypatch.setattr("cli.commands.runtime.requests.post", _post)

    cmd_runtime(Namespace(project=project_id, subcommand="status"))
    out1 = capsys.readouterr().out
    assert project_id in out1

    cmd_runtime(Namespace(project=project_id, subcommand="reconcile"))
    out2 = capsys.readouterr().out
    assert (project_id in out2) or ("Docker unavailable" in out2)

    client.delete(f"/projects/{project_id}")
