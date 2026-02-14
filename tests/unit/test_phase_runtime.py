from types import SimpleNamespace
from pathlib import Path
import shutil

from langchain_core.messages import AIMessage

from gods.agents.phase_runtime import AgentPhaseRuntime, PhaseToolPolicy, _base_phases
from gods.config import runtime_config, ProjectConfig, AgentModelConfig


def test_base_phases_match_new_state_machine():
    phases = _base_phases()
    assert [p.name for p in phases] == ["reason", "act", "observe"]
    assert "finalize" not in phases[1].allowed_tools
    assert phases[2].allowed_tools == ("finalize",)


def test_policy_blocks_finalize_in_action():
    policy = PhaseToolPolicy(
        phase_allow_map={"act": {"write_file", "run_command"}, "observe": {"finalize"}},
        disabled_tools=set(),
        max_repeat_same_call=2,
        explore_budget=99,
    )
    reason = policy.check("act", "finalize", {})
    assert reason is not None
    assert "not allowed" in reason


class _SequenceBrain:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def think_with_tools(self, llm_messages, tools, trace_meta=None):
        out = self.responses[self.calls]
        self.calls += 1
        return out


class _DummyAgent:
    def __init__(self, project_id: str, agent_id: str, brain):
        self.project_id = project_id
        self.agent_id = agent_id
        self.agent_dir = Path("projects") / project_id / "agents" / agent_id
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        (self.agent_dir / "agent.md").write_text("# tester", encoding="utf-8")
        self.brain = brain
        self.executed_tools = []
        self.memory_log = []

    def build_context(self, **kwargs):
        return "ctx"

    def get_tools(self):
        return []

    def _append_to_memory(self, text: str):
        self.memory_log.append(text)

    def _load_local_memory(self):
        return ""

    def execute_tool(self, name: str, args: dict) -> str:
        self.executed_tools.append((name, args))
        return f"ok:{name}"


def test_action_phase_executes_multiple_tool_calls():
    project_id = "unit_phase_multi_tools"
    agent_id = "tester"
    responses = [
        AIMessage(content="reason plan", tool_calls=[]),
        AIMessage(
            content="do work",
            tool_calls=[
                {"id": "t1", "name": "write_file", "args": {"path": "a.py", "content": "x=1\n"}},
                {"id": "t2", "name": "run_command", "args": {"command": "python -m pytest -q"}},
            ],
        ),
        AIMessage(content="not done yet", tool_calls=[]),
    ]
    agent = _DummyAgent(project_id, agent_id, _SequenceBrain(responses))
    runtime = AgentPhaseRuntime(agent)
    state = {"messages": [], "next_step": "", "project_id": project_id}
    try:
        out = runtime.run(state, simulation_directives="", local_memory="", inbox_msgs="")
        assert out["next_step"] == "continue"
        assert [name for name, _ in agent.executed_tools] == ["write_file", "run_command"]
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_observe_finalize_finishes():
    project_id = "unit_phase_observe_finalize"
    agent_id = "tester"
    responses = [
        AIMessage(content="reason plan", tool_calls=[]),
        AIMessage(content="action done", tool_calls=[{"id": "t1", "name": "write_file", "args": {"path": "x.txt", "content": "ok"}}]),
        AIMessage(content="all complete", tool_calls=[{"id": "t2", "name": "finalize", "args": {}}]),
    ]
    agent = _DummyAgent(project_id, agent_id, _SequenceBrain(responses))
    runtime = AgentPhaseRuntime(agent)
    state = {"messages": [], "next_step": "", "project_id": project_id}
    try:
        out = runtime.run(state, simulation_directives="", local_memory="", inbox_msgs="")
        assert out["next_step"] == "finish"
        assert [name for name, _ in agent.executed_tools] == ["write_file", "finalize"]
        rs = (agent.agent_dir / "runtime_state.json").read_text(encoding="utf-8")
        assert '"phase_idx": 0' in rs
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_reason_tool_calls_are_blocked_not_executed():
    project_id = "unit_phase_reason_block"
    agent_id = "tester"
    responses = [
        AIMessage(content="bad reason", tool_calls=[{"id": "t1", "name": "list_dir", "args": {}}]),
        AIMessage(content="reason fixed", tool_calls=[]),
        AIMessage(content="act no-op", tool_calls=[]),
        AIMessage(content="observe continue", tool_calls=[]),
    ]
    agent = _DummyAgent(project_id, agent_id, _SequenceBrain(responses))
    runtime = AgentPhaseRuntime(agent)
    state = {"messages": [], "next_step": "", "project_id": project_id}
    try:
        out = runtime.run(state, simulation_directives="", local_memory="", inbox_msgs="")
        assert out["next_step"] == "continue"
        assert agent.executed_tools == []
        assert any("Policy Block" in m for m in agent.memory_log)
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_observe_non_finalize_tool_is_blocked():
    project_id = "unit_phase_observe_block"
    agent_id = "tester"
    responses = [
        AIMessage(content="reason", tool_calls=[]),
        AIMessage(content="act", tool_calls=[{"id": "a1", "name": "write_file", "args": {"path": "x.txt", "content": "ok"}}]),
        AIMessage(content="observe", tool_calls=[{"id": "t1", "name": "list_dir", "args": {}}]),
        AIMessage(content="observe retry no tool", tool_calls=[]),
    ]
    agent = _DummyAgent(project_id, agent_id, _SequenceBrain(responses))
    runtime = AgentPhaseRuntime(agent)
    state = {"messages": [], "next_step": "", "project_id": project_id}
    try:
        out = runtime.run(state, simulation_directives="", local_memory="", inbox_msgs="")
        assert out["next_step"] == "continue"
        assert [name for name, _ in agent.executed_tools] == ["write_file"]
        assert any("Tool 'list_dir' is not allowed in phase 'observe'" in m for m in agent.memory_log)
        assert any("[PHASE_RETRY] observe" in m for m in agent.memory_log)
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_reason_tool_call_triggers_retry_feedback():
    project_id = "unit_phase_reason_retry"
    agent_id = "tester"
    responses = [
        AIMessage(content="reason bad", tool_calls=[{"id": "r1", "name": "list_dir", "args": {}}]),
        AIMessage(content="reason fixed plan only", tool_calls=[]),
        AIMessage(content="act", tool_calls=[]),
        AIMessage(content="observe", tool_calls=[]),
    ]
    agent = _DummyAgent(project_id, agent_id, _SequenceBrain(responses))
    runtime = AgentPhaseRuntime(agent)
    state = {"messages": [], "next_step": "", "project_id": project_id}
    try:
        out = runtime.run(state, simulation_directives="", local_memory="", inbox_msgs="")
        assert out["next_step"] == "continue"
        assert any("[PHASE_RETRY] reason" in m for m in agent.memory_log)
        assert agent.executed_tools == []
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_act_without_tool_call_is_rejected_in_strict_mode():
    project_id = "unit_phase_act_no_tool"
    agent_id = "tester"
    responses = [
        AIMessage(content="reason ok", tool_calls=[]),
        AIMessage(content="act no tool", tool_calls=[]),
    ]
    agent = _DummyAgent(project_id, agent_id, _SequenceBrain(responses))
    runtime = AgentPhaseRuntime(agent)
    state = {"messages": [], "next_step": "", "project_id": project_id}
    try:
        out = runtime.run(state, simulation_directives="", local_memory="", inbox_msgs="")
        assert out["next_step"] == "continue"
        assert any("[PHASE_RETRY] act" in m for m in agent.memory_log)
        assert agent.executed_tools == []
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_iterative_action_strategy_supports_multiple_action_observe_cycles():
    project_id = "unit_phase_iterative_strategy"
    agent_id = "tester"
    responses = [
        AIMessage(content="reason ok", tool_calls=[]),
        AIMessage(content="act1", tool_calls=[{"id": "a1", "name": "write_file", "args": {"path": "a.txt", "content": "1"}}]),
        AIMessage(content="observe1 incomplete", tool_calls=[]),
        AIMessage(content="act2", tool_calls=[{"id": "a2", "name": "write_file", "args": {"path": "b.txt", "content": "2"}}]),
        AIMessage(content="observe2 complete", tool_calls=[{"id": "f1", "name": "finalize", "args": {}}]),
    ]
    old_projects = runtime_config.projects.copy()
    runtime_config.projects[project_id] = ProjectConfig(
        name="iterative-test",
        active_agents=[agent_id],
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
        phase_strategy="iterative_action",
        phase_interaction_max=3,
    )
    agent = _DummyAgent(project_id, agent_id, _SequenceBrain(responses))
    runtime = AgentPhaseRuntime(agent)
    state = {"messages": [], "next_step": "", "project_id": project_id}
    try:
        out = runtime.run(state, simulation_directives="", local_memory="", inbox_msgs="")
        assert out["next_step"] == "finish"
        assert [name for name, _ in agent.executed_tools] == ["write_file", "write_file", "finalize"]
    finally:
        runtime_config.projects = old_projects
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_iterative_action_allows_first_diagnostic_then_requires_productive():
    project_id = "unit_phase_iterative_productive_threshold"
    agent_id = "tester"
    responses = [
        AIMessage(content="reason ok", tool_calls=[]),
        AIMessage(content="act1 diagnose", tool_calls=[{"id": "a1", "name": "read_file", "args": {"path": "models/book.py"}}]),
        AIMessage(content="observe1 not done", tool_calls=[]),
        AIMessage(content="act2 still diagnose", tool_calls=[{"id": "a2", "name": "list_dir", "args": {}}]),
    ]
    old_projects = runtime_config.projects.copy()
    runtime_config.projects[project_id] = ProjectConfig(
        name="iterative-threshold-test",
        active_agents=[agent_id],
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
        phase_strategy="iterative_action",
        phase_interaction_max=3,
        phase_act_require_tool_call=True,
        phase_act_require_productive_tool=True,
        phase_act_productive_from_interaction=2,
    )
    agent = _DummyAgent(project_id, agent_id, _SequenceBrain(responses))
    runtime = AgentPhaseRuntime(agent)
    state = {"messages": [], "next_step": "", "project_id": project_id}
    try:
        out = runtime.run(state, simulation_directives="", local_memory="", inbox_msgs="")
        assert out["next_step"] == "continue"
        assert [name for name, _ in agent.executed_tools] == ["read_file"]
        assert any("[PHASE_RETRY] act" in m for m in agent.memory_log)
    finally:
        runtime_config.projects = old_projects
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
