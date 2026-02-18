from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from gods.config import runtime_config

client = TestClient(app)


def test_config_api_redacts_openrouter_key():
    old_real_key = runtime_config.openrouter_api_key
    raw_key = "sk-test-redaction-1234567890"
    cfg = client.get("/config").json()

    try:
        payload = dict(cfg)
        payload["openrouter_api_key"] = raw_key
        res = client.post("/config/save", json=payload)
        assert res.status_code == 200
        assert "warnings" in res.json()

        out = client.get("/config").json()
        assert out.get("has_openrouter_api_key") is True
        redacted = out.get("openrouter_api_key", "")
        assert redacted != raw_key
        assert redacted.endswith(raw_key[-4:])
    finally:
        payload = client.get("/config").json()
        payload["openrouter_api_key"] = old_real_key
        client.post("/config/save", json=payload)


def test_config_save_returns_deprecated_warnings():
    cfg = client.get("/config").json()
    pid = cfg.get("current_project", "default")
    payload = dict(cfg)
    payload["projects"][pid]["autonomous_batch_size"] = 4
    out = client.post("/config/save", json=payload)
    assert out.status_code == 200
    body = out.json()
    warnings = body.get("warnings", [])
    assert isinstance(warnings, list)
    assert any("autonomous_batch_size" in w for w in warnings)


def test_config_save_rejects_node_tools_write():
    cfg = client.get("/config").json()
    pid = cfg.get("current_project", "default")
    payload = dict(cfg)
    payload["projects"][pid]["node_tools"] = {"global": ["list"]}
    out = client.post("/config/save", json=payload)
    assert out.status_code == 400
    assert f"projects.{pid}.node_tools" in str(out.json())
    assert "unknown key" in str(out.json())
