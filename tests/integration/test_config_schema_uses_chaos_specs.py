from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def test_config_schema_tool_policy_uses_metis_spec():
    res = client.get("/config/schema")
    assert res.status_code == 200
    data = res.json() or {}
    fields = data.get("fields", {}) or {}
    project_fields = fields.get("project", []) or []
    tool_policy = next((x for x in project_fields if x.get("key") == "tool_policies"), None)
    assert tool_policy is not None
    ui = tool_policy.get("ui", {}) or {}
    assert ui.get("spec_source") == "gods.metis.strategy_specs"
    strategy_phases = ui.get("strategy_phases", {}) or {}
    assert strategy_phases.get("react_graph") == ["global"]
    assert strategy_phases.get("freeform") == ["global"]
