from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from gods.config import runtime_config

client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


def test_project_report_build_and_show_api():
    project_id = "test_project_report_api_world"
    old_project = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)

        protocol_dir = Path("projects") / project_id / "protocols"
        protocol_dir.mkdir(parents=True, exist_ok=True)
        (protocol_dir / "registry.json").write_text(
            json.dumps({"protocols": [{"name": "ground.integrate"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        (protocol_dir / "contracts.json").write_text(
            json.dumps({"contracts": [{"title": "Ecosystem Contract", "version": "1.0.0"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        with (protocol_dir / "invocations.jsonl").open("w", encoding="utf-8") as f:
            f.write(json.dumps({"name": "ground.integrate", "status": "succeeded", "caller_id": "sheep"}) + "\n")
            f.write(json.dumps({"name": "ground.integrate", "status": "succeeded", "caller_id": "tiger"}) + "\n")

        runtime_dir = Path("projects") / project_id / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "ports.json").write_text(
            json.dumps({"leases": [{"owner_id": "ground_api", "port": 18081}]}, ensure_ascii=False),
            encoding="utf-8",
        )

        build = client.post(f"/projects/{project_id}/report/build")
        assert build.status_code == 200
        payload = build.json()
        assert payload["project_id"] == project_id
        assert payload["protocol_count"] == 1
        assert payload["invocation_count"] == 2
        assert Path(payload["output"]["json"]).exists()
        assert Path(payload["output"]["md"]).exists()

        show = client.get(f"/projects/{project_id}/report")
        assert show.status_code == 200
        report = show.json()
        assert report["project_id"] == project_id
        assert report["contract_count"] == 1
        assert report["status_summary"]["succeeded"] == 2
        assert report["port_leases_summary"]["lease_count"] == 1
    finally:
        _switch_project(old_project)
        client.delete(f"/projects/{project_id}")
        mirror = Path("reports") / f"project_{project_id}_latest.md"
        if mirror.exists():
            mirror.unlink()
