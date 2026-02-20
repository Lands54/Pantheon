from __future__ import annotations

import shutil
from pathlib import Path

from gods.agents.base import GodAgent
from gods.chaos.snapshot import build_resource_snapshot
from gods.config import AgentModelConfig, ProjectConfig, runtime_config
from gods.mnemosyne.facade import intent_from_inbox_received


def test_chaos_mailbox_attachment_render_only_summary():
    project_id = "it_chaos_mailbox_att"
    agent_id = "receiver"
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="chaos",
        active_agents=[agent_id],
        agent_settings={agent_id: AgentModelConfig()},
    )
    base = Path("projects") / project_id
    profile = base / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text("# receiver", encoding="utf-8")
    try:
        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        inbox_intent = intent_from_inbox_received(
            project_id=project_id,
            agent_id=agent_id,
            title="t",
            sender="sender",
            message_id="m1",
            content="body",
            attachments=["artf_1234567890ab_1234567890123"],
            payload={},
            msg_type="private",
        )
        snapshot = build_resource_snapshot(
            agent,
            {
                "project_id": project_id,
                "agent_id": agent_id,
                "triggers": [],
                "mailbox": [inbox_intent],
                "messages": [],
                "context": "",
            },
        )
        buckets = dict(snapshot.context_materials.get("card_buckets", {}) or {})
        rows = list(buckets.get("mailbox", []) or [])
        assert rows
        text = "\n".join([str(x.get("text", "") or "") for x in rows if isinstance(x, dict)])
        assert "MAILBOX_ATTACHMENTS" in text
        assert "body" not in text
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(base, ignore_errors=True)
