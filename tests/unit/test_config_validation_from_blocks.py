from gods.config.registry_catalog import CONFIG_REGISTRY


def test_validation_rejects_unknown_project_key():
    try:
        CONFIG_REGISTRY.validate_payload({"projects": {"default": {"unknown_x": 1}}})
    except ValueError as e:
        assert "unknown key" in str(e)
        return
    raise AssertionError("expected ValueError")


def test_validation_warns_deprecated_key():
    warnings = CONFIG_REGISTRY.validate_payload(
        {"projects": {"default": {"autonomous_batch_size": 4, "phase_strategy": "react_graph"}}}
    )
    assert any("deprecated config used" in w for w in warnings)
