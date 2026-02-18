from __future__ import annotations

import pytest

import gods.agents.llm_control as llm_control
from gods.agents.brain import GodBrain
from gods.config import AgentModelConfig, ProjectConfig, runtime_config
from langchain_core.messages import HumanMessage


def test_llm_control_plane_concurrency_timeout():
    project_id = "unit_llm_control_concurrency"
    old_projects = runtime_config.projects.copy()
    runtime_config.projects[project_id] = ProjectConfig(
        name="llm-control",
        active_agents=["a"],
        agent_settings={"a": AgentModelConfig()},
        llm_control_enabled=True,
        llm_global_max_concurrency=1,
        llm_project_max_concurrency=1,
        llm_global_rate_per_minute=1000,
        llm_project_rate_per_minute=1000,
        llm_acquire_timeout_sec=1,
        llm_retry_interval_ms=50,
    )
    plane = llm_control.LLMControlPlane()
    t1 = plane.acquire(project_id)
    try:
        with pytest.raises(llm_control.LLMControlAcquireTimeout):
            plane.acquire(project_id)
    finally:
        t1.release()
        runtime_config.projects = old_projects


def test_llm_control_plane_rate_timeout_with_fake_clock(monkeypatch):
    project_id = "unit_llm_control_rate"
    old_projects = runtime_config.projects.copy()
    runtime_config.projects[project_id] = ProjectConfig(
        name="llm-control",
        active_agents=["a"],
        agent_settings={"a": AgentModelConfig()},
        llm_control_enabled=True,
        llm_global_max_concurrency=10,
        llm_project_max_concurrency=10,
        llm_global_rate_per_minute=1,
        llm_project_rate_per_minute=1,
        llm_acquire_timeout_sec=2,
        llm_retry_interval_ms=100,
    )
    now = {"t": 1000.0}

    monkeypatch.setattr(llm_control.time, "time", lambda: now["t"])
    monkeypatch.setattr(llm_control.time, "sleep", lambda sec: now.__setitem__("t", now["t"] + float(sec)))

    plane = llm_control.LLMControlPlane()
    t1 = plane.acquire(project_id)
    try:
        with pytest.raises(llm_control.LLMControlAcquireTimeout):
            plane.acquire(project_id)
    finally:
        t1.release()
        runtime_config.projects = old_projects


def test_brain_returns_error_when_llm_control_timeout(monkeypatch):
    project_id = "unit_brain_llm_control_timeout"
    agent_id = "tester"
    old_projects = runtime_config.projects.copy()
    old_key = runtime_config.openrouter_api_key
    runtime_config.projects[project_id] = ProjectConfig(
        name="llm-control",
        active_agents=[agent_id],
        agent_settings={agent_id: AgentModelConfig()},
    )
    runtime_config.openrouter_api_key = "test-key"
    brain = GodBrain(agent_id=agent_id, project_id=project_id)
    monkeypatch.setattr(
        llm_control.llm_control_plane,
        "acquire",
        lambda project_id: (_ for _ in ()).throw(llm_control.LLMControlAcquireTimeout("timeout")),
    )
    out = brain.think_with_tools([HumanMessage(content="hello")], tools=[])
    assert "timeout" in str(out.content)
    runtime_config.openrouter_api_key = old_key
    runtime_config.projects = old_projects
