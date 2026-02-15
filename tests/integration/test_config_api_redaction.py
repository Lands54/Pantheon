from __future__ import annotations

from fastapi.testclient import TestClient

from api.server import app
from gods.config import runtime_config

client = TestClient(app)


def test_config_api_redacts_openrouter_key():
    old_real_key = runtime_config.openrouter_api_key
    raw_key = "sk-test-redaction-1234567890"
    cfg = client.get("/config").json()

    try:
        payload = dict(cfg)
        payload["openrouter_api_key"] = raw_key
        client.post("/config/save", json=payload)

        out = client.get("/config").json()
        assert out.get("has_openrouter_api_key") is True
        redacted = out.get("openrouter_api_key", "")
        assert redacted != raw_key
        assert redacted.endswith(raw_key[-4:])
    finally:
        payload = client.get("/config").json()
        payload["openrouter_api_key"] = old_real_key
        client.post("/config/save", json=payload)
