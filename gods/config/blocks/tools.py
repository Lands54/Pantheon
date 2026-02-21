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
        module_id="tools",
        module_title="Tools",
        scope="project",
        group_id="tools",
        group_title="Tools",
        fields=[
            ConfigFieldDecl("tool_loop_max", "project", "integer", 8, False, "单次脉冲工具调用上限。", "project-runtime", ["gods/agents/runtime/engine.py"], constraints={"min": 1, "max": 64}),
            ConfigFieldDecl("tool_policies", "project", "object", {}, False, "项目级策略/阶段工具白名单（推荐主路径）。", "project-runtime", ["gods/agents/base.py"], ui=_tool_policies_ui()),
            ConfigFieldDecl("agent_settings", "project", "object", {}, False, "按 agent_id 的运行覆盖配置。", "project-runtime", ["gods/agents/base.py", "gods/agents/brain.py"]),
            ConfigFieldDecl("hermes_allow_agent_tool_provider", "project", "boolean", False, False, "允许 agent_tool 作为 Hermes provider。", "project-runtime", ["gods/hermes/policy.py", "api/services/hermes_service.py"]),
        ],
    ),
]
