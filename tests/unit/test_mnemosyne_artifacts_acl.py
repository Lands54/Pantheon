from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gods.mnemosyne import facade as mnemosyne_facade


def _cleanup(project_id: str):
    shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
    shutil.rmtree(Path("projects") / "_global", ignore_errors=True)


def test_artifact_acl_scope_matrix():
    project_id = "unit_artifact_acl"
    _cleanup(project_id)
    try:
        ref_project = mnemosyne_facade.put_artifact_text(
            scope="project",
            project_id=project_id,
            owner_agent_id="",
            actor_id="alpha",
            text="hello",
            mime="text/plain",
            tags=[],
        )
        assert ref_project.artifact_id.startswith("artf_")
        _ = mnemosyne_facade.head_artifact(ref_project.artifact_id, actor_id="beta", project_id=project_id)
        with pytest.raises(Exception):
            _ = mnemosyne_facade.head_artifact(ref_project.artifact_id, actor_id="beta", project_id="other_project")

        ref_agent = mnemosyne_facade.put_artifact_text(
            scope="agent",
            project_id=project_id,
            owner_agent_id="alpha",
            actor_id="alpha",
            text="private",
            mime="text/plain",
            tags=[],
        )
        _ = mnemosyne_facade.head_artifact(ref_agent.artifact_id, actor_id="alpha", project_id=project_id)
        with pytest.raises(Exception):
            _ = mnemosyne_facade.head_artifact(ref_agent.artifact_id, actor_id="beta", project_id=project_id)

        with pytest.raises(Exception):
            _ = mnemosyne_facade.put_artifact_text(
                scope="global",
                project_id=project_id,
                owner_agent_id="",
                actor_id="alpha",
                text="x",
                mime="text/plain",
                tags=[],
            )
        ref_global = mnemosyne_facade.put_artifact_text(
            scope="global",
            project_id=project_id,
            owner_agent_id="",
            actor_id="human",
            text="shared",
            mime="text/plain",
            tags=[],
        )
        _ = mnemosyne_facade.head_artifact(ref_global.artifact_id, actor_id="beta", project_id=project_id)
    finally:
        _cleanup(project_id)

