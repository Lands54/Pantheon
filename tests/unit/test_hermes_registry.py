from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from gods.hermes.facade import HermesRegistry
from gods.hermes.facade import ProtocolSpec


def test_hermes_registry_register_and_get():
    project_id = f"hermes_reg_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        reg = HermesRegistry()
        spec = ProtocolSpec(
            name="grass.get_biomass",
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
        loaded = reg.get(project_id, "grass.get_biomass")
        assert loaded.name == "grass.get_biomass"
        assert loaded.provider.agent_id == "grass"
    finally:
        if base.exists():
            shutil.rmtree(base)


def test_hermes_registry_re_register_overwrites_same_name():
    project_id = f"hermes_reg_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        reg = HermesRegistry()
        v1 = ProtocolSpec(
            name="grass.sync_state",
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
        same = [r for r in rows if r.name == "grass.sync_state"]
        assert len(same) == 1
        assert same[0].provider.url.endswith("/sync/v2")
    finally:
        if base.exists():
            shutil.rmtree(base)


def test_hermes_registry_re_register_different_content_is_allowed():
    project_id = f"hermes_reg_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        reg = HermesRegistry()
        a = ProtocolSpec(
            name="grass.scan",
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
        reg.register(project_id, b)
        loaded = reg.get(project_id, "grass.scan")
        assert loaded.provider.url.endswith("/b")
    finally:
        if base.exists():
            shutil.rmtree(base)
