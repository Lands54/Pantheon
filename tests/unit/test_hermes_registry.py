from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from gods.hermes.registry import HermesRegistry
from gods.hermes.models import ProtocolSpec


def test_hermes_registry_register_and_get():
    project_id = f"hermes_reg_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        reg = HermesRegistry()
        spec = ProtocolSpec(
            name="grass.get_biomass",
            version="1.0.0",
            provider={
                "type": "agent_tool",
                "project_id": project_id,
                "agent_id": "grass",
                "tool_name": "list_dir",
            },
            request_schema={"type": "object"},
            response_schema={"type": "object", "required": ["result"], "properties": {"result": {"type": "string"}}},
        )
        reg.register(project_id, spec)
        loaded = reg.get(project_id, "grass.get_biomass", "1.0.0")
        assert loaded.name == "grass.get_biomass"
        assert loaded.provider.agent_id == "grass"
    finally:
        if base.exists():
            shutil.rmtree(base)
