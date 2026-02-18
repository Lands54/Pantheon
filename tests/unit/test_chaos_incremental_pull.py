from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

from gods.agents.base import GodAgent
from gods.chaos.snapshot import pull_incremental_materials
from gods.config import AgentModelConfig, ProjectConfig, runtime_config


def _setup_profile(project_id: str, agent_id: str):
    profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(f"# {agent_id}\nchaos incremental test", encoding="utf-8")


def test_pull_incremental_materials_updates_state(monkeypatch):
    project_id = "unit_chaos_incremental"
    agent_id = "solo"
    _setup_profile(project_id, agent_id)
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="chaos inc",
        active_agents=[agent_id],
        phase_strategy="react_graph",
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
        simulation_enabled=False,
    )

    monkeypatch.setattr("gods.chaos.snapshot.has_pending", lambda pid, aid: True)
    monkeypatch.setattr(
        "gods.chaos.snapshot.fetch_mailbox_intents",
        lambda pid, aid, budget: [
            SimpleNamespace(
                intent_key="inbox.received.unread",
                project_id=pid,
                agent_id=aid,
                source_kind="inbox",
                payload={"message_id": "m1"},
            )
        ],
    )

    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        state = {
            "project_id": project_id,
            "agent_id": agent_id,
            "triggers": [],
            "mailbox": [],
            "__worker_claim_events": lambda limit=50: [
                {
                    "event_id": "e1",
                    "project_id": project_id,
                    "agent_id": agent_id,
                    "event_type": "manual",
                    "payload": {"reason": "manual"},
                    "priority": 80,
                    "state": "queued",
                    "attempt": 0,
                    "max_attempts": 3,
                    "created_at": 0.0,
                    "available_at": 0.0,
                }
            ],
        }
        patch = pull_incremental_materials(agent, state)
        assert len(state["triggers"]) == 1
        assert len(state["mailbox"]) == 1
        inc = ((patch or {}).get("runtime_meta", {}) or {}).get("incremental_pull", {})
        assert inc.get("new_trigger_count") == 1
        assert inc.get("new_mailbox_count") == 1
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
