from __future__ import annotations

from langchain_core.messages import HumanMessage

from gods.agents.brain import GodBrain
from gods.config import runtime_config


def test_brain_blocks_real_llm_import_under_pytest_by_default(monkeypatch):
    old_key = runtime_config.openrouter_api_key
    runtime_config.openrouter_api_key = "test-key"
    try:
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
        monkeypatch.delenv("GODS_ENABLE_LLM_UNDER_PYTEST", raising=False)
        monkeypatch.delenv("AGENT_BENCH_LIVE", raising=False)
        monkeypatch.delenv("AGENT_BENCH_LIVE_STRICT", raising=False)

        brain = GodBrain(agent_id="tester", project_id="default")
        out = brain.think_with_tools([HumanMessage(content="hi")], tools=[])
        assert "LLM import is disabled under pytest by default" in str(out.content)
    finally:
        runtime_config.openrouter_api_key = old_key

