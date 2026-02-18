from __future__ import annotations

from fastapi.testclient import TestClient
import base64

from api.app import app
from gods.config import runtime_config
from gods.mnemosyne import facade as mnemosyne_facade


client = TestClient(app)


def _switch_project(project_id: str):
    cfg = client.get("/config").json()
    cfg["current_project"] = project_id
    client.post("/config/save", json=cfg)


def test_mnemosyne_artifact_head_and_list_api():
    project_id = "it_mnemo_art_api"
    old = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)
        ref = mnemosyne_facade.put_artifact_text(
            scope="project",
            project_id=project_id,
            owner_agent_id="",
            actor_id="human",
            text="api-test",
            mime="text/plain",
            tags=[],
        )
        lst = client.get(
            "/mnemosyne/artifacts",
            params={"project_id": project_id, "scope": "project", "actor_id": "human", "limit": 10},
        )
        assert lst.status_code == 200
        assert any(x.get("artifact_id") == ref.artifact_id for x in lst.json().get("items", []))

        head = client.get(
            f"/mnemosyne/artifacts/{ref.artifact_id}",
            params={"project_id": project_id, "actor_id": "human"},
        )
        assert head.status_code == 200
        assert head.json().get("artifact", {}).get("artifact_id") == ref.artifact_id
    finally:
        _switch_project(old)
        client.delete(f"/projects/{project_id}")


def test_mnemosyne_artifact_put_text_and_bytes_api():
    project_id = "it_mnemo_art_put_api"
    old = runtime_config.current_project
    try:
        client.post("/projects/create", json={"id": project_id})
        _switch_project(project_id)
        p1 = client.post(
            "/mnemosyne/artifacts/text",
            json={
                "project_id": project_id,
                "scope": "project",
                "owner_agent_id": "",
                "actor_id": "human",
                "content": "hello-text",
                "mime": "text/plain",
                "tags": ["x"],
            },
        )
        assert p1.status_code == 200
        aid1 = p1.json().get("artifact", {}).get("artifact_id", "")
        assert aid1.startswith("artf_")

        p2 = client.post(
            "/mnemosyne/artifacts/bytes",
            json={
                "project_id": project_id,
                "scope": "project",
                "owner_agent_id": "",
                "actor_id": "human",
                "mime": "application/json",
                "tags": ["a", "b"],
                "content_base64": base64.b64encode(b'{"k":1}').decode("utf-8"),
            },
        )
        assert p2.status_code == 200
        aid2 = p2.json().get("artifact", {}).get("artifact_id", "")
        assert aid2.startswith("artf_")
    finally:
        _switch_project(old)
        client.delete(f"/projects/{project_id}")
