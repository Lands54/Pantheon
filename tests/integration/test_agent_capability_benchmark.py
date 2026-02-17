from __future__ import annotations

import json
import shutil
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from gods.agents.base import GodAgent
from gods.config import AgentModelConfig, ProjectConfig, runtime_config
from gods.iris.service import enqueue_message, list_outbox_receipts
from gods.angelia.pulse.scheduler_hooks import inject_inbox_before_pulse


class _ScriptedBrain:
    """Deterministic brain for capability benchmark."""

    def __init__(self):
        self.turn = 0
        self.system_prompts: list[str] = []

    def think_with_tools(self, messages, tools, trace_meta=None):
        self.system_prompts.append(str(getattr(messages[0], "content", "") if messages else ""))
        script = [
            AIMessage(
                content="先确认工作目录",
                tool_calls=[{"id": "tc_1", "name": "list_dir", "args": {"path": "."}}],
            ),
            AIMessage(
                content="给对方回信确认",
                tool_calls=[
                    {
                        "id": "tc_2",
                        "name": "send_message",
                        "args": {
                            "to_id": "peer",
                            "title": "ack-bootstrap",
                            "message": "收到任务，开始执行。",
                        },
                    }
                ],
            ),
            AIMessage(
                content="检查发件回执",
                tool_calls=[
                    {
                        "id": "tc_3",
                        "name": "check_outbox",
                        "args": {"status": "pending", "limit": 20},
                    }
                ],
            ),
            AIMessage(content="done", tool_calls=[]),
        ]
        idx = min(self.turn, len(script) - 1)
        self.turn += 1
        return script[idx]


def _read_observations(project_id: str, agent_id: str) -> list[dict]:
    p = Path("projects") / project_id / "mnemosyne" / "observations" / f"{agent_id}.jsonl"
    if not p.exists():
        return []
    rows: list[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _capability_metrics(rows: list[dict]) -> dict:
    tracked = {"list_dir", "send_message", "check_outbox"}
    filtered = [r for r in rows if str(r.get("tool", "")) in tracked]
    total = len(filtered)
    ok = sum(1 for r in filtered if str(r.get("status", "")) == "ok")
    error = sum(1 for r in filtered if str(r.get("status", "")) == "error")
    blocked = sum(1 for r in filtered if str(r.get("status", "")) == "blocked")
    by_tool: dict[str, int] = {}
    for r in filtered:
        name = str(r.get("tool", ""))
        by_tool[name] = by_tool.get(name, 0) + 1
    return {
        "total_calls": total,
        "ok_calls": ok,
        "error_calls": error,
        "blocked_calls": blocked,
        "accuracy": (ok / total) if total else 0.0,
        "by_tool": by_tool,
    }


def test_agent_capability_benchmark_inbox_reply_and_tool_accuracy():
    project_id = "it_agent_capability_benchmark"
    agent_id = "bench"
    agent_dir = Path("projects") / project_id / "agents" / agent_id
    peer_dir = Path("projects") / project_id / "agents" / "peer"
    agent_dir.mkdir(parents=True, exist_ok=True)
    peer_dir.mkdir(parents=True, exist_ok=True)

    profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / f"{agent_id}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text("# bench\n执行收信、回信与工具调用验证。", encoding="utf-8")
    peer_profile = Path("projects") / project_id / "mnemosyne" / "agent_profiles" / "peer.md"
    peer_profile.write_text("# peer\n被动接收消息。", encoding="utf-8")

    old = runtime_config.projects.get(project_id)
    runtime_config.projects[project_id] = ProjectConfig(
        name="it capability benchmark",
        active_agents=[agent_id, "peer"],
        agent_settings={
            agent_id: AgentModelConfig(disabled_tools=[]),
            "peer": AgentModelConfig(disabled_tools=[]),
        },
        simulation_enabled=False,
        phase_mode_enabled=True,
        phase_strategy="freeform",
        tool_loop_max=6,
        context_strategy="structured_v1",
        context_budget_state_window=18000,
        context_state_window_limit=80,
    )
    try:
        enqueue_message(
            project_id=project_id,
            agent_id=agent_id,
            sender="tester",
            title="bootstrap-task",
            content="请确认并回信。",
            msg_type="private",
            trigger_pulse=False,
            pulse_priority=100,
        )

        state = {
            "project_id": project_id,
            "messages": [HumanMessage(content="pulse", name="system")],
            "context": "agent capability benchmark",
            "next_step": "",
        }
        inject_inbox_before_pulse(state, project_id=project_id, agent_id=agent_id)

        agent = GodAgent(agent_id=agent_id, project_id=project_id)
        brain = _ScriptedBrain()
        agent.brain = brain
        out = agent.process(state)
        assert out.get("next_step") == "finish"

        assert brain.system_prompts, "system prompt should be captured"
        first_prompt = brain.system_prompts[0]
        assert "# COMBINED MEMORY" in first_prompt
        assert "[INBOX UNREAD]" in first_prompt
        assert "bootstrap-task" in first_prompt

        obs = _read_observations(project_id, agent_id)
        metrics = _capability_metrics(obs)
        assert metrics["total_calls"] >= 3
        assert metrics["by_tool"].get("list_dir", 0) >= 1
        assert metrics["by_tool"].get("send_message", 0) >= 1
        assert metrics["by_tool"].get("check_outbox", 0) >= 1
        assert metrics["accuracy"] >= 0.66

        outbox = list_outbox_receipts(
            project_id=project_id,
            from_agent_id=agent_id,
            to_agent_id="peer",
            limit=50,
        )
        assert any(x.title == "ack-bootstrap" for x in outbox)
    finally:
        if old is None:
            runtime_config.projects.pop(project_id, None)
        else:
            runtime_config.projects[project_id] = old
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
