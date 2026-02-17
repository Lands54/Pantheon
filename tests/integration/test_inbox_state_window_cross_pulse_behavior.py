from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from gods.agents.base import GodAgent
from gods.config import AgentModelConfig, ProjectConfig, runtime_config
from gods.iris.facade import enqueue_message
from gods.angelia.facade import inject_inbox_before_pulse


class _CapturePromptBrain:
    def __init__(self, reply: str = "done"):
        self.prompts: list[str] = []
        self.reply = reply

    def think_with_tools(self, messages, tools, trace_meta=None):
        self.prompts.append(str(getattr(messages[0], "content", "") if messages else ""))
        return AIMessage(content=self.reply, tool_calls=[])


def _mk_project(project_id: str, agent_id: str):
    (Path("projects") / project_id / "agents" / agent_id).mkdir(parents=True, exist_ok=True)
    p = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# alpha\ntest", encoding="utf-8")


def test_inbox_can_appear_in_next_pulse_when_reusing_same_state():
    project_id = f"it_inbox_state_reuse_{uuid.uuid4().hex[:6]}"
    agent_id = "alpha"
    _mk_project(project_id, agent_id)

    old = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        active_agents=[agent_id],
        phase_strategy="freeform",
        tool_loop_max=2,
        context_strategy="structured_v1",
        context_budget_state_window=20000,
        context_state_window_limit=80,
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
    )
    try:
        enqueue_message(
            project_id=project_id,
            agent_id=agent_id,
            sender="tester",
            title="short-lived-inbox",
            content="hello from inbox",
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )
        state = {
            "project_id": project_id,
            "messages": [HumanMessage(content="pulse1", name="system")],
            "context": "ctx",
            "next_step": "",
        }
        inject_inbox_before_pulse(state, project_id=project_id, agent_id=agent_id)
        injected_texts = [
            str(getattr(m, "content", ""))
            for m in state.get("messages", [])
            if str(getattr(m, "name", "")) == "event_inbox"
        ]
        assert injected_texts and "short-lived-inbox" in injected_texts[-1]

        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        brain = _CapturePromptBrain()
        agent.brain = brain

        # Pulse 1 with inbox injection.
        agent.process(state)
        assert brain.prompts and "[INBOX" in brain.prompts[-1]

        # Pulse 2 reusing same state object: previous event_inbox SystemMessage can remain in state_window.
        state["messages"].append(HumanMessage(content="pulse2", name="system"))
        state["next_step"] = ""
        agent.process(state)
        assert "short-lived-inbox" in brain.prompts[-1]
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)


def test_inbox_is_persisted_across_fresh_pulses_with_state_window_store():
    project_id = f"it_inbox_state_fresh_{uuid.uuid4().hex[:6]}"
    agent_id = "alpha"
    _mk_project(project_id, agent_id)

    old = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        active_agents=[agent_id],
        phase_strategy="freeform",
        tool_loop_max=2,
        context_strategy="structured_v1",
        context_budget_state_window=20000,
        context_state_window_limit=80,
        agent_settings={agent_id: AgentModelConfig(disabled_tools=[])},
    )
    try:
        enqueue_message(
            project_id=project_id,
            agent_id=agent_id,
            sender="tester",
            title="fresh-state-inbox",
            content="hello from inbox",
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )

        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        brain = _CapturePromptBrain()
        agent.brain = brain

        # Pulse 1 with injected inbox.
        state1 = {
            "project_id": project_id,
            "messages": [HumanMessage(content="pulse1", name="system")],
            "context": "ctx",
            "next_step": "",
        }
        inject_inbox_before_pulse(state1, project_id=project_id, agent_id=agent_id)
        injected_texts = [
            str(getattr(m, "content", ""))
            for m in state1.get("messages", [])
            if str(getattr(m, "name", "")) == "event_inbox"
        ]
        assert injected_texts and "fresh-state-inbox" in injected_texts[-1]
        agent.process(state1)
        assert brain.prompts and "[INBOX" in brain.prompts[-1]

        # Pulse 2 uses a new/fresh state (same pattern as angelia worker _run_agent()).
        # With persistent state_window store, last pulse context should still be visible.
        state2 = {
            "project_id": project_id,
            "messages": [HumanMessage(content="pulse2", name="system")],
            "context": "ctx",
            "next_step": "",
        }
        agent.process(state2)
        assert "fresh-state-inbox" in brain.prompts[-1]
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
