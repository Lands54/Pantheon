from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gods.config import ProjectConfig, runtime_config
from gods.runtime.detach.service import DetachError, submit


def test_detach_backend_guard_and_disable(monkeypatch):
    project_id = "unit_detach_guard"
    old = runtime_config.projects.get(project_id)
    shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
    try:
        runtime_config.projects[project_id] = ProjectConfig(
            command_executor="local",
            docker_enabled=True,
            detach_enabled=True,
        )

        with pytest.raises(DetachError) as e1:
            submit(project_id=project_id, agent_id="alpha", command="echo hi")
        assert e1.value.code == "DETACH_BACKEND_UNSUPPORTED"

        runtime_config.projects[project_id].command_executor = "docker"
        runtime_config.projects[project_id].detach_enabled = False
        with pytest.raises(DetachError) as e2:
            submit(project_id=project_id, agent_id="alpha", command="echo hi")
        assert e2.value.code == "DETACH_DISABLED"

        runtime_config.projects[project_id].detach_enabled = True
        with pytest.raises(DetachError) as e3:
            submit(project_id=project_id, agent_id="alpha", command="echo hi; rm -rf /")
        assert e3.value.code == "DETACH_COMMAND_INVALID"

        monkeypatch.setattr("gods.runtime.detach.service.start_job", lambda *a, **k: True)
        res = submit(project_id=project_id, agent_id="alpha", command="echo hi")
        assert res.get("ok") is True
        assert res.get("job_id")
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)

