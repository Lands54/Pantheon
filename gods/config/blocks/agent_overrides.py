from __future__ import annotations

from gods.metis.strategy_specs import export_strategy_default_tools, export_strategy_phase_map
from gods.config.declarations import ConfigBlockDecl, ConfigFieldDecl


_STRATEGY_PHASES = export_strategy_phase_map()
_RUNTIME_NODE_DEFAULT_TOOLS = export_strategy_default_tools()


def _tool_policies_ui() -> dict:
    return {
        "widget": "strategy_phase_tool_allowlist",
        "strategy_phases": _STRATEGY_PHASES,
        "strategy_default_tools": _RUNTIME_NODE_DEFAULT_TOOLS,
        "fixed_phases": True,
        "spec_source": "gods.metis.strategy_specs",
    }


CONFIG_BLOCKS: list[ConfigBlockDecl] = [
    ConfigBlockDecl(
        module_id="agent_overrides",
        module_title="Agent Overrides",
        scope="agent",
        group_id="agent",
        group_title="Agent Overrides",
        default_collapsed=True,
        fields=[
            ConfigFieldDecl("model", "agent", "string", "stepfun/step-3.5-flash:free", False, "Agent 模型名。", "agent-runtime", ["gods/agents/brain.py"]),
            ConfigFieldDecl("disabled_tools", "agent", "array", ["check_inbox", "check_outbox", "post_to_synod", "mnemo_write_agent", "mnemo_list_agent", "mnemo_read_agent"], False, "该 agent 禁用工具列表。", "agent-runtime", ["gods/agents/base.py", "gods/agents/tool_policy.py"]),
            ConfigFieldDecl("phase_strategy", "agent", "string", None, True, "该 agent 的 phase 策略覆盖。", "agent-runtime", ["gods/agents/runtime/engine.py"], enum=["react_graph", "freeform"]),
            ConfigFieldDecl("context_strategy", "agent", "string", None, True, "该 agent 的 context 策略覆盖。", "agent-runtime", ["gods/janus/context_policy.py"], enum=["sequential_v1"]),
            ConfigFieldDecl("context_token_budget_total", "agent", "integer", None, True, "该 agent 的上下文预算覆盖。", "agent-runtime", ["gods/janus/context_policy.py"]),
            ConfigFieldDecl("metis_refresh_mode", "agent", "string", None, True, "该 agent 的 Metis 刷新模式覆盖。", "agent-runtime", ["gods/metis/snapshot.py"], enum=["pulse", "node"]),
            ConfigFieldDecl("tool_policies", "agent", "object", {}, False, "该 agent 的策略/阶段工具白名单覆盖。", "agent-runtime", ["gods/agents/base.py"], ui=_tool_policies_ui()),
        ],
    ),
]
