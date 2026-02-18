from __future__ import annotations

from gods.config.models import AgentModelConfig, ProjectConfig, SystemConfig
from gods.config.registry_catalog import CONFIG_REGISTRY


def _keys(scope: str) -> set[str]:
    return {e.key for e in CONFIG_REGISTRY.entries(scope)}


def test_registry_covers_models_and_no_extra_keys():
    assert _keys("system") == set(SystemConfig.model_fields.keys())
    assert _keys("project") == set(ProjectConfig.model_fields.keys())
    assert _keys("agent") == set(AgentModelConfig.model_fields.keys())


def test_registry_entries_have_required_metadata():
    for scope in ("system", "project", "agent"):
        for e in CONFIG_REGISTRY.entries(scope):
            assert e.description.strip()
            assert e.owner.strip()
            if e.status != "deprecated":
                assert e.runtime_used_by, f"missing runtime_used_by for {scope}.{e.key}"


def test_registry_validate_payload_warns_deprecated():
    warnings = CONFIG_REGISTRY.validate_payload(
        {
            "projects": {
                "default": {
                    "phase_strategy": "react_graph",
                    "autonomous_batch_size": 4,
                }
            }
        }
    )
    assert any("autonomous_batch_size" in w for w in warnings)


def test_registry_validate_payload_rejects_unknown():
    try:
        CONFIG_REGISTRY.validate_payload(
            {
                "projects": {
                    "default": {
                        "phase_strategy": "react_graph",
                        "does_not_exist": 1,
                    }
                }
            }
        )
    except ValueError as e:
        assert "unknown key" in str(e)
        return
    raise AssertionError("expected ValueError")
