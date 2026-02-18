from __future__ import annotations

import pytest

from gods.config.registry_catalog import CONFIG_REGISTRY


def test_registry_rejects_project_node_tools():
    with pytest.raises(ValueError, match="projects.default.node_tools"):
        CONFIG_REGISTRY.validate_payload(
            {
                "projects": {
                    "default": {
                        "node_tools": {"global": ["list"]},
                    }
                }
            }
        )


def test_registry_rejects_agent_node_tools():
    with pytest.raises(ValueError, match="projects.default.agent_settings.alpha.node_tools"):
        CONFIG_REGISTRY.validate_payload(
            {
                "projects": {
                    "default": {
                        "agent_settings": {
                            "alpha": {
                                "node_tools": {"global": ["list"]},
                            }
                        }
                    }
                }
            }
        )
