from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gods.agents.base import GodAgent
from gods.chaos.snapshot import build_resource_snapshot
from gods.config import AgentModelConfig, ProjectConfig, runtime_config
from gods.mnemosyne.facade import CHAOS_CARD_BUCKET_KEYS, validate_card_buckets


def _setup_profile(project_id: str, agent_id: str):
    profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(f"# {agent_id}\nchaos card buckets test", encoding="utf-8")


def test_chaos_card_buckets_contract():
    project_id = "unit_chaos_card_buckets"
    agent_id = "solo"
    _setup_profile(project_id, agent_id)
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="chaos snapshot",
        active_agents=[agent_id],
        phase_strategy="react_graph",
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
        simulation_enabled=False,
    )
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        state = {
            "project_id": project_id,
            "agent_id": agent_id,
            "strategy": "react_graph",
            "messages": [],
            "mailbox": [],
            "triggers": [],
            "__pulse_meta": {"pulse_id": "p1"},
        }
        snapshot = build_resource_snapshot(agent, state, strategy="react_graph")
        materials = dict(snapshot.context_materials or {})
        assert set(materials.keys()) == {"intent_seq_latest", "card_buckets"}
        buckets = dict(materials.get("card_buckets") or {})
        assert set(buckets.keys()) == set(CHAOS_CARD_BUCKET_KEYS)
        for key in CHAOS_CARD_BUCKET_KEYS:
            rows = list(buckets.get(key, []) or [])
            assert rows, f"{key} bucket should not be empty"
            for row in rows:
                assert isinstance(row, dict)
                assert row.get("card_id")
                assert row.get("kind")
                assert isinstance(row.get("source_intent_ids"), list)
                assert isinstance(row.get("source_intent_seq_max"), int)
        mailbox_rows = list(buckets.get("mailbox", []) or [])
        assert mailbox_rows
        assert all(str(x.get("card_id", "")).startswith("material.mailbox:") for x in mailbox_rows)
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_chaos_card_buckets_rejects_undeclared_non_intent_card():
    row = {
        "card_id": "material.not_declared",
        "kind": "task",
        "priority": 10,
        "text": "x",
        "source_intent_ids": [],
        "source_intent_seq_max": 0,
        "derived_from_card_ids": [],
        "supersedes_card_ids": [],
        "compression_type": "",
        "meta": {},
        "created_at": 1.0,
    }
    buckets = {k: [] for k in CHAOS_CARD_BUCKET_KEYS}
    buckets["profile"] = [row]
    with pytest.raises(ValueError, match="material_cards_registry.json"):
        validate_card_buckets(buckets)
