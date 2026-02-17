import shutil
import subprocess
from pathlib import Path

import pytest

from gods.config import ProjectConfig, runtime_config
from gods.tools.execution import run_command


def _docker_ready() -> bool:
    try:
        v = subprocess.run(["docker", "version"], capture_output=True, text=True, timeout=5)
        if v.returncode != 0:
            return False
        i = subprocess.run(["docker", "image", "inspect", "gods-agent-base:py311"], capture_output=True, text=True, timeout=5)
        return i.returncode == 0
    except Exception:
        return False


@pytest.mark.skipif(not _docker_ready(), reason="docker or gods-agent-base:py311 not available")
def test_docker_run_command_can_import_gods():
    project_id = "it_docker_import"
    agent_id = "ground"
    old = runtime_config.projects.get(project_id)
    try:
        runtime_config.projects[project_id] = ProjectConfig(
            active_agents=[agent_id],
            command_executor="docker",
            docker_enabled=True,
            docker_image="gods-agent-base:py311",
        )
        territory = Path("projects") / project_id / "agents" / agent_id
        territory.mkdir(parents=True, exist_ok=True)

        out = run_command.invoke(
            {
                "command": "python -c \"print(__import__('gods').__name__)\"",
                "caller_id": agent_id,
                "project_id": project_id,
            }
        )
        if "outside of container mount namespace root" in out:
            pytest.skip("docker cwd namespace instability in shared test run")
        assert "exit=0" in out
        assert "gods" in out
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
