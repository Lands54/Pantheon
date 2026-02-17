import json
import shutil
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from gods.agents.brain import GodBrain
from gods.config import runtime_config, ProjectConfig, AgentModelConfig
from gods.paths import runtime_debug_dir


def test_llm_trace_writer_persists_request_and_response():
    project_id = "unit_brain_trace"
    agent_id = "tester"
    agent_dir = Path("projects") / project_id / "agents" / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "agent.md").write_text("# tester", encoding="utf-8")

    old_projects = runtime_config.projects.copy()
    runtime_config.projects[project_id] = ProjectConfig(
        name="trace",
        active_agents=[agent_id],
        agent_settings={agent_id: AgentModelConfig()},
        debug_llm_trace_enabled=True,
    )
    try:
        brain = GodBrain(agent_id=agent_id, project_id=project_id)
        req = [SystemMessage(content="sys"), HumanMessage(content="hello")]
        resp = AIMessage(content="ok")
        brain._write_llm_trace(
            mode="tools",
            model="stepfun/step-3.5-flash:free",
            request_messages=req,
            tools=[],
            response_message=resp,
            trace_meta={"pulse_id": "p1", "reason": "test"},
        )
        trace_path = runtime_debug_dir(project_id, agent_id) / "llm_io.jsonl"
        assert trace_path.exists()
        row = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[-1])
        assert row["pulse_id"] == "p1"
        assert row["reason"] == "test"
        assert row["mode"] == "tools"
        assert row["request_messages"][0]["content"] == "sys"
        assert row["response"]["content"] == "ok"
    finally:
        runtime_config.projects = old_projects
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_think_with_tools_applies_configured_llm_delay(monkeypatch):
    project_id = "unit_brain_delay"
    agent_id = "tester"
    old_projects = runtime_config.projects.copy()
    runtime_config.projects[project_id] = ProjectConfig(
        name="delay",
        active_agents=[agent_id],
        agent_settings={agent_id: AgentModelConfig()},
        llm_call_delay_sec=2,
    )
    old_key = runtime_config.openrouter_api_key
    runtime_config.openrouter_api_key = "test-key"

    class _FakeLLM:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            return AIMessage(content="ok")

    sleep_calls: list[float] = []

    try:
        brain = GodBrain(agent_id=agent_id, project_id=project_id)
        monkeypatch.setattr(brain, "get_llm", lambda: (_FakeLLM(), "fake-model"))
        monkeypatch.setattr(brain, "_write_llm_trace", lambda *args, **kwargs: None)
        monkeypatch.setattr("gods.agents.brain.time.sleep", lambda x: sleep_calls.append(float(x)))

        response = brain.think_with_tools([HumanMessage(content="hi")], tools=[])

        assert response.content == "ok"
        assert sleep_calls == [2.0]
    finally:
        runtime_config.openrouter_api_key = old_key
        runtime_config.projects = old_projects
