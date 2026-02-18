from __future__ import annotations

import shutil
from pathlib import Path

from gods.config import AgentModelConfig, ProjectConfig, runtime_config
from gods.interaction.facade import submit_message_event
from gods.iris import facade as iris_facade
from gods.mnemosyne import facade as mnemosyne_facade


def test_send_message_with_artifacts_roundtrip():
    project_id = "it_send_msg_artifacts"
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="it-artifacts",
        active_agents=["sender", "receiver", "intruder"],
        agent_settings={
            "sender": AgentModelConfig(),
            "receiver": AgentModelConfig(),
            "intruder": AgentModelConfig(),
        },
    )
    try:
        ref = mnemosyne_facade.put_artifact_text(
            scope="agent",
            project_id=project_id,
            owner_agent_id="sender",
            actor_id="sender",
            text="# contract",
            mime="text/markdown",
            tags=["contract"],
        )
        try:
            _ = mnemosyne_facade.head_artifact(ref.artifact_id, "receiver", project_id)
            assert False, "receiver should not read before explicit grant"
        except Exception:
            pass
        out = submit_message_event(
            project_id=project_id,
            to_id="receiver",
            sender_id="sender",
            title="with-attachment",
            content="please read",
            msg_type="private",
            trigger_pulse=False,
            priority=100,
            attachments=[ref.artifact_id],
        )
        assert out["state"] == "done"
        _ = mnemosyne_facade.head_artifact(ref.artifact_id, "receiver", project_id)
        try:
            _ = mnemosyne_facade.head_artifact(ref.artifact_id, "intruder", project_id)
            assert False, "intruder should not read without explicit grant"
        except Exception:
            pass

        intents = iris_facade.fetch_mailbox_intents(project_id, "receiver", budget=10)
        rows = [x for x in intents if str(getattr(x, "intent_key", "")) == "inbox.received.unread"]
        assert rows
        payload = dict(getattr(rows[0], "payload", {}) or {})
        assert payload.get("attachments") == [ref.artifact_id]
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
