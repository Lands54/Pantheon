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
def test_docker_runtime_agent_territory_isolation():
    project_id = "it_docker_isolation"
    old = runtime_config.projects.get(project_id)
    try:
        runtime_config.projects[project_id] = ProjectConfig(
            active_agents=["ground", "sheep"],
            command_executor="docker",
            docker_enabled=True,
            docker_image="gods-agent-base:py311",
        )

        g = Path("projects") / project_id / "agents" / "ground"
        s = Path("projects") / project_id / "agents" / "sheep"
        g.mkdir(parents=True, exist_ok=True)
        s.mkdir(parents=True, exist_ok=True)
        (s / "secret.txt").write_text("sheep-secret", encoding="utf-8")

        out = run_command.invoke(
            {
                "command": "python -c \"from pathlib import Path; print(Path('../sheep/secret.txt').exists())\"",
                "caller_id": "ground",
                "project_id": project_id,
            }
        )
        assert "exit=0" in out
        assert "False" in out
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
