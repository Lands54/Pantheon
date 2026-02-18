from __future__ import annotations

import shutil
from pathlib import Path

from gods.mnemosyne import facade as mnemosyne_facade


def test_artifact_store_put_get_materialize_and_dedupe():
    project_id = "unit_artifact_store"
    base = Path("projects") / project_id
    shutil.rmtree(base, ignore_errors=True)
    try:
        r1 = mnemosyne_facade.put_artifact_text(
            scope="project",
            project_id=project_id,
            owner_agent_id="",
            actor_id="alpha",
            text='{"k":1}',
            mime="application/json",
            tags=["contract"],
        )
        r2 = mnemosyne_facade.put_artifact_text(
            scope="project",
            project_id=project_id,
            owner_agent_id="",
            actor_id="alpha",
            text='{"k":1}',
            mime="application/json",
            tags=["contract"],
        )
        assert r1.artifact_id == r2.artifact_id
        got = mnemosyne_facade.get_artifact_bytes(r1.artifact_id, actor_id="beta", project_id=project_id)
        assert got.decode("utf-8") == '{"k":1}'
        out = mnemosyne_facade.materialize_artifact(
            r1.artifact_id,
            actor_id="beta",
            project_id=project_id,
            target_dir=str(base / "tmp"),
        )
        assert Path(out).exists()
        listed = mnemosyne_facade.list_artifacts("project", project_id, actor_id="beta", limit=10)
        assert any(x.artifact_id == r1.artifact_id for x in listed)
    finally:
        shutil.rmtree(base, ignore_errors=True)

