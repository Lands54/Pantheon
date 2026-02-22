from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from gods.agents.brain import GodBrain, LLMInvocationError
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
        with pytest.raises(LLMInvocationError, match="LLM import is disabled under pytest by default"):
            brain.think_with_tools([HumanMessage(content="hi")], tools=[])
    finally:
        runtime_config.openrouter_api_key = old_key
