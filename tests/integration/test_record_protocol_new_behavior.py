from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from gods.config import runtime_config, ProjectConfig
from gods.tools.communication import record_protocol


def test_record_protocol_is_deprecated_and_no_longer_registers():
    project_id = f"rp_new_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        runtime_config.projects[project_id] = ProjectConfig(hermes_allow_agent_tool_provider=True)
        agent_dir = base / "agents" / "alpha"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "agent.md").write_text("# alpha", encoding="utf-8")

        msg = record_protocol.invoke(
            {
                "topic": "ecosystem",
                "relation": "run_command",
                "object": "simulator",
                "clause": "统一通过命令行执行",
                "counterparty": "ground",
                "status": "agreed",
                "caller_id": "alpha",
                "project_id": project_id,
            }
        )
        assert "Protocol Deprecated" in msg
        assert "register_contract" in msg

        registry = base / "protocols" / "registry.json"
        assert not registry.exists()

        old_events = base / "protocols" / "events.jsonl"
        assert not old_events.exists()
    finally:
        runtime_config.projects.pop(project_id, None)
        if base.exists():
            shutil.rmtree(base)
