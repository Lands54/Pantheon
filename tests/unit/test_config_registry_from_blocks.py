from gods.config.models import AgentModelConfig, ProjectConfig, SystemConfig
from gods.config.registry_catalog import CONFIG_REGISTRY


def _keys(scope: str) -> set[str]:
    return {e.key for e in CONFIG_REGISTRY.entries(scope)}


def test_registry_covers_models_and_no_extra_keys_from_blocks():
    assert _keys("system") == set(SystemConfig.model_fields.keys())
    assert _keys("project") == set(ProjectConfig.model_fields.keys())
    assert _keys("agent") == set(AgentModelConfig.model_fields.keys())


def test_schema_has_module_groups():
    schema = CONFIG_REGISTRY.export_schema(tool_options=[])
    module_groups = schema.get("module_groups", [])
    assert isinstance(module_groups, list)
    assert module_groups
    assert all("id" in row and "keys" in row for row in module_groups)
