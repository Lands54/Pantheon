from __future__ import annotations

from argparse import Namespace
from pathlib import Path
import shutil

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from api.app import app
from cli.commands.context import cmd_context
from gods.agents.base import GodAgent
from gods.config import AgentModelConfig, ProjectConfig, runtime_config

client = TestClient(app)


class _Resp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


class _FakeBrain:
    def think_with_tools(self, messages, tools, trace_meta=None):
        return AIMessage(content="done", tool_calls=[])


def test_context_preview_api_and_cli(monkeypatch, capsys):
    pid = "it_context_preview"
    aid = "alpha"
    agent_dir = Path("projects") / pid / "agents" / aid
    agent_dir.mkdir(parents=True, exist_ok=True)
    profile = Path("projects") / pid / "mnemosyne" / "agent_profiles" / f"{aid}.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text("# alpha", encoding="utf-8")

    old = runtime_config.projects.get(pid)
    runtime_config.projects[pid] = ProjectConfig(
        active_agents=[aid],
        context_strategy="structured_v1",
        agent_settings={aid: AgentModelConfig(disabled_tools=[])},
    )
    old_cur = runtime_config.current_project
    runtime_config.current_project = pid
    try:
        agent = GodAgent(agent_id=aid, project_id=pid)
        agent.brain = _FakeBrain()
        state = {
            "project_id": pid,
            "messages": [HumanMessage(content="start", name="h")],
            "context": "objective",
            "next_step": "",
        }
        agent.process(state)

        api_res = client.get(f"/projects/{pid}/context/preview", params={"agent_id": aid})
        assert api_res.status_code == 200
        payload = api_res.json()
        assert payload.get("preview") is not None

        snap_full = client.get(f"/projects/{pid}/context/snapshot", params={"agent_id": aid, "since_intent_seq": 0})
        assert snap_full.status_code == 200
        s0 = snap_full.json()
        assert s0.get("available") is True
        assert s0.get("mode") == "pulse_ledger"
        assert isinstance(s0.get("entries"), list)
        assert isinstance(s0.get("pulses"), list)
        base = int(s0.get("base_intent_seq", 0) or 0)

        snap_delta = client.get(
            f"/projects/{pid}/context/snapshot",
            params={"agent_id": aid, "since_intent_seq": max(1, base)},
        )
        assert snap_delta.status_code == 200
        s1 = snap_delta.json()
        assert s1.get("available") in {True, False}
        assert s1.get("mode") == "pulse_ledger"
        assert isinstance(s1.get("entries"), list)
        assert isinstance(s1.get("errors"), list)
        assert isinstance(s1.get("warnings"), list)

        comp = client.get(f"/projects/{pid}/context/snapshot/compressions", params={"agent_id": aid, "limit": 20})
        assert comp.status_code == 200
        c0 = comp.json()
        assert isinstance(c0.get("items"), list)
        assert bool(c0.get("deprecated")) is True

        def _get(url, params=None, timeout=0):
            if url.endswith("/config"):
                return _Resp({"current_project": pid})
            path = url.replace("http://localhost:8000", "")
            return _Resp(client.get(path, params=params).json())

        monkeypatch.setattr("cli.commands.context.requests.get", _get)
        cmd_context(Namespace(project=pid, subcommand="preview", agent=aid, limit=20))
        out = capsys.readouterr().out
        assert "strategy_used" in out
    finally:
        runtime_config.current_project = old_cur
        if old is None:
            runtime_config.projects.pop(pid, None)
        else:
            runtime_config.projects[pid] = old
        shutil.rmtree(Path("projects") / pid, ignore_errors=True)
