from gods.config.blocks import AGENT_DEFAULTS, PROJECT_DEFAULTS, SYSTEM_DEFAULTS
from gods.config.models import AgentModelConfig, ProjectConfig, SystemConfig


def test_model_defaults_follow_block_defaults():
    proj = ProjectConfig()
    agent = AgentModelConfig()
    syscfg = SystemConfig()

    assert proj.simulation_interval_min == PROJECT_DEFAULTS["simulation_interval_min"]
    assert proj.context_strategy == PROJECT_DEFAULTS["context_strategy"]
    assert proj.llm_request_timeout_sec == PROJECT_DEFAULTS["llm_request_timeout_sec"]

    assert agent.model == AGENT_DEFAULTS["model"]
    assert agent.disabled_tools == AGENT_DEFAULTS["disabled_tools"]

    assert syscfg.current_project == SYSTEM_DEFAULTS["current_project"]
    assert "default" in syscfg.projects
