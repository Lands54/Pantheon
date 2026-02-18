from __future__ import annotations

import shutil
from pathlib import Path

from gods.agents.orchestrators.themis import ThemisOrchestrator
from gods.config import AgentModelConfig, ProjectConfig, runtime_config


class _FakeTool:
    def __init__(self, name: str):
        self.name = name
        self.args = ["path"]
        self.description = f"{name} desc"

    def invoke(self, args: dict):
        if self.name == "boom":
            raise RuntimeError("boom")
        return f"ok:{self.name}:{args.get('path', '')}"


def test_themis_allowlist_and_execution_records():
    project_id = "unit_themis_executor"
    agent_id = "solo"
    base = Path("projects") / project_id
    old = runtime_config.projects.get(project_id)
    intents: list = []
    observations: list[tuple[str, str]] = []
    runtime_config.projects[project_id] = ProjectConfig(
        active_agents=[agent_id],
        phase_strategy="react_graph",
        tool_policies={"react_graph": {"global": ["alpha"]}},
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
        simulation_enabled=False,
    )
    try:
        executor = ThemisOrchestrator(
            project_id=project_id,
            agent_id=agent_id,
            agent_dir=base / "agents" / agent_id,
            tools_provider=lambda: [_FakeTool("alpha"), _FakeTool("boom")],
            intent_recorder=lambda x: intents.append(x),
            observation_recorder=lambda name, _args, _res, st: observations.append((name, st)),
        )
        names = [t.name for t in executor.get_tools_for_node("dispatch_tools")]
        assert names == ["alpha"]

        ok = executor.execute_tool("alpha", {"path": "."}, node_name="dispatch_tools")
        assert "ok:alpha:." in ok
        assert observations[-1] == ("alpha", "ok")
        assert intents[-1].intent_key == "tool.alpha.ok"

        blocked = executor.execute_tool("boom", {"path": "."}, node_name="dispatch_tools")
        assert "not allowed in node" in blocked
        assert observations[-1] == ("boom", "blocked")
        assert intents[-1].intent_key == "tool.boom.blocked"
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old
        shutil.rmtree(base, ignore_errors=True)
