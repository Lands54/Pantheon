from langchain_core.messages import HumanMessage

from gods.janus.facade import ContextBuildRequest, StructuredV1ContextStrategy


def test_structured_v1_uses_dynamic_recent_budget_not_fixed_8(tmp_path, monkeypatch):
    req = ContextBuildRequest(
        project_id="p_struct_budget",
        agent_id="a",
        state={"messages": [HumanMessage(content=("x" * 50), name="h") for _ in range(30)], "context": "obj"},
        directives="# a",
        local_memory="local mem",
        inbox_hint="inbox",
        phase_name="act",
        tools_desc="- [[list(path)]]",
        context_cfg={
            "budget_task_state": 1000,
            "budget_observations": 1000,
            "budget_inbox": 1000,
            "budget_state_window": 2000,
            "state_window_limit": 30,
            "observation_window": 10,
            "include_inbox_status_hints": True,
        },
    )
    res = StructuredV1ContextStrategy().build(req)
    assert res.strategy_used == "structured_v1"
    assert len(res.recent_messages) == 0
    assert res.token_usage["state_window_messages"] > 8
    assert "[STATE_WINDOW]" in "\n\n".join(res.system_blocks)
