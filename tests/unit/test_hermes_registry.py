from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from gods.hermes.registry import HermesRegistry
from gods.hermes.models import ProtocolSpec
from gods.hermes.errors import HermesError


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


def test_hermes_registry_auto_disables_old_active_version():
    project_id = f"hermes_reg_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        reg = HermesRegistry()
        v1 = ProtocolSpec(
            name="grass.sync_state",
            version="1.0.0",
            provider={
                "type": "http",
                "project_id": project_id,
                "url": "http://127.0.0.1:18081/sync/v1",
                "method": "POST",
            },
            request_schema={"type": "object"},
            response_schema={"type": "object"},
        )
        v2 = ProtocolSpec(
            name="grass.sync_state",
            version="1.1.0",
            provider={
                "type": "http",
                "project_id": project_id,
                "url": "http://127.0.0.1:18081/sync/v2",
                "method": "POST",
            },
            request_schema={"type": "object"},
            response_schema={"type": "object"},
        )
        reg.register(project_id, v1)
        reg.register(project_id, v2)
        rows = reg.list(project_id)
        active = [r for r in rows if r.name == "grass.sync_state" and r.status == "active"]
        assert len(active) == 1
        assert active[0].version == "1.1.0"
    finally:
        if base.exists():
            shutil.rmtree(base)


def test_hermes_registry_same_version_conflicting_content_rejected():
    project_id = f"hermes_reg_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        reg = HermesRegistry()
        a = ProtocolSpec(
            name="grass.scan",
            version="1.0.0",
            provider={
                "type": "http",
                "project_id": project_id,
                "url": "http://127.0.0.1:18081/a",
                "method": "POST",
            },
            request_schema={"type": "object"},
            response_schema={"type": "object"},
        )
        b = ProtocolSpec(
            name="grass.scan",
            version="1.0.0",
            provider={
                "type": "http",
                "project_id": project_id,
                "url": "http://127.0.0.1:18081/b",
                "method": "POST",
            },
            request_schema={"type": "object"},
            response_schema={"type": "object"},
        )
        reg.register(project_id, a)
        try:
            reg.register(project_id, b)
            assert False, "expected conflicting same-version register to fail"
        except HermesError as e:
            assert "conflict" in e.message.lower()
    finally:
        if base.exists():
            shutil.rmtree(base)
