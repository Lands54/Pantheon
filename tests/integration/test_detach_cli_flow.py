from __future__ import annotations

from argparse import Namespace

from fastapi.testclient import TestClient

from api.app import app
from cli.commands.detach import cmd_detach

client = TestClient(app)


class _Resp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def test_detach_cli_flow(monkeypatch, capsys):
    project_id = "it_detach_cli"
    client.post("/projects/create", json={"id": project_id})
    try:
        cfg = client.get("/config").json()
        cfg["current_project"] = project_id
        cfg["projects"][project_id]["command_executor"] = "docker"
        cfg["projects"][project_id]["docker_enabled"] = True
        cfg["projects"][project_id]["detach_enabled"] = True
        client.post("/config/save", json=cfg)

        monkeypatch.setattr("gods.runtime.detach.service.start_job", lambda *a, **k: True)

        def _get(url, params=None, timeout=0):
            if url.endswith("/config"):
                return _Resp(client.get("/config").json())
            path = url.replace("http://localhost:8000", "")
            return _Resp(client.get(path, params=params).json())

        def _post(url, json=None, timeout=0):
            path = url.replace("http://localhost:8000", "")
            return _Resp(client.post(path, json=json).json())

        monkeypatch.setattr("cli.commands.detach.requests.get", _get)
        monkeypatch.setattr("cli.commands.detach.requests.post", _post)

        cmd_detach(Namespace(project=project_id, subcommand="submit", agent="genesis", cmd="echo hi"))
        out1 = capsys.readouterr().out
        assert "job_id" in out1

        cmd_detach(Namespace(project=project_id, subcommand="list", agent="", status="", limit=20))
        out2 = capsys.readouterr().out
        assert "items" in out2

        # read current submitted detach event for stop/logs
        events = client.get(
            "/events",
            params={
                "project_id": project_id,
                "domain": "runtime",
                "event_type": "detach_submitted_event",
                "limit": 20,
            },
        ).json().get("items", [])
        assert events
        job_id = str((events[-1].get("payload") or {}).get("job_id", ""))
        assert job_id

        cmd_detach(Namespace(project=project_id, subcommand="stop", job_id=job_id))
        out3 = capsys.readouterr().out
        assert "project_id" in out3

        cmd_detach(Namespace(project=project_id, subcommand="logs", job_id=job_id))
        capsys.readouterr()
    finally:
        client.delete(f"/projects/{project_id}")
