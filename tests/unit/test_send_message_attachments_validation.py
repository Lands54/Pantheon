from __future__ import annotations

import shutil
from pathlib import Path

from gods.config import AgentModelConfig, ProjectConfig, runtime_config
from gods.mnemosyne import facade as mnemosyne_facade
from gods.tools.comm_human import send_message


def test_send_message_attachments_validation():
    project_id = "unit_send_msg_att"
    old_project = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="att",
        active_agents=["sender", "receiver"],
        agent_settings={
            "sender": AgentModelConfig(),
            "receiver": AgentModelConfig(),
        },
    )
    base = Path("projects") / project_id
    shutil.rmtree(base, ignore_errors=True)
    try:
        bad_path = send_message.invoke(
            {
                "to_id": "receiver",
                "title": "t",
                "message": "m",
                "caller_id": "sender",
                "project_id": project_id,
                "attachments": '["/tmp/a.md"]',
            }
        )
        assert "path-like values are forbidden" in bad_path

        bad_id = send_message.invoke(
            {
                "to_id": "receiver",
                "title": "t",
                "message": "m",
                "caller_id": "sender",
                "project_id": project_id,
                "attachments": '["abc"]',
            }
        )
        assert "invalid attachment id" in bad_id

        ref = mnemosyne_facade.put_artifact_text(
            scope="agent",
            project_id=project_id,
            owner_agent_id="sender",
            actor_id="sender",
            text="hello",
            mime="text/plain",
            tags=[],
        )
        ok = send_message.invoke(
            {
                "to_id": "receiver",
                "title": "t",
                "message": "m",
                "caller_id": "sender",
                "project_id": project_id,
                "attachments": f'["{ref.artifact_id}"]',
            }
        )
        assert "attachments_count=1" in ok
    finally:
        if old_project is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old_project
        shutil.rmtree(base, ignore_errors=True)
