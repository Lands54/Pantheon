from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

from gods.config import runtime_config, ProjectConfig
from gods.hermes.facade import HermesExecutor
from gods.hermes.facade import InvokeRequest, ProtocolSpec


def test_hermes_executor_async_job_lifecycle():
    project_id = f"hermes_async_{uuid.uuid4().hex[:8]}"
    base = Path("projects") / project_id
    try:
        runtime_config.projects[project_id] = ProjectConfig(hermes_allow_agent_tool_provider=True)
        agent_dir = base / "agents" / "alpha"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "agent.md").write_text("# alpha\nasync tester", encoding="utf-8")

        exe = HermesExecutor()
        spec = ProtocolSpec(
            name="alpha.list",
            mode="both",
            provider={
                "type": "agent_tool",
                "project_id": project_id,
                "agent_id": "alpha",
                "tool_name": "list_dir",
            },
            request_schema={"type": "object"},
            response_schema={"type": "object", "required": ["result"], "properties": {"result": {"type": "string"}}},
        )
        exe.registry.register(project_id, spec)

        result = exe.invoke_async(
            InvokeRequest(
                project_id=project_id,
                caller_id="tester",
                name="alpha.list",
                mode="async",
                payload={"path": "."},
            )
        )
        assert result.ok is True
        assert result.job_id

        status = None
        for _ in range(20):
            job = exe.get_job(project_id, result.job_id)
            if job and job.status in {"succeeded", "failed"}:
                status = job.status
                break
            time.sleep(0.1)

        assert status in {"succeeded", "failed"}
    finally:
        runtime_config.projects.pop(project_id, None)
        if base.exists():
            shutil.rmtree(base)
