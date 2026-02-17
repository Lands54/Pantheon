from gods.janus.context_policy import resolve_context_cfg
from gods.config import AgentModelConfig, ProjectConfig, runtime_config


def test_context_config_resolution_project_and_agent_override():
    pid = "unit_context_cfg"
    aid = "a"
    old = runtime_config.projects.get(pid)
    try:
        runtime_config.projects[pid] = ProjectConfig(
            context_strategy="structured_v1",
            context_token_budget_total=28000,
            agent_settings={
                aid: AgentModelConfig(
                    context_strategy="structured_v1",
                    context_token_budget_total=16000,
                )
            },
        )
        cfg = resolve_context_cfg(pid, aid)
        assert cfg["strategy"] == "structured_v1"
        assert cfg["token_budget_total"] == 16000
        assert cfg["budget_task_state"] == 4000
    finally:
        if old is None:
            runtime_config.projects.pop(pid, None)
        else:
            runtime_config.projects[pid] = old
