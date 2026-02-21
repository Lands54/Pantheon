from __future__ import annotations

from gods.config.declarations import ConfigBlockDecl, ConfigFieldDecl


CONFIG_BLOCKS: list[ConfigBlockDecl] = [
    ConfigBlockDecl(
        module_id="project_core",
        module_title="Project Core",
        scope="project",
        group_id="project_core",
        group_title="Project Core",
        fields=[
            ConfigFieldDecl("name", "project", "string", None, True, "项目展示名称。", "project-runtime", ["api/services/project_service.py"]),
            ConfigFieldDecl("active_agents", "project", "array", [], False, "项目激活 agent 列表。", "project-runtime", ["api/services/project_service.py", "api/services/angelia_service.py"]),
            ConfigFieldDecl("phase_strategy", "project", "string", "react_graph", False, "项目策略流程名。", "project-runtime", ["gods/agents/runtime/engine.py", "cli/commands/agent.py"], enum=["react_graph", "freeform"]),
        ],
    ),
    ConfigBlockDecl(
        module_id="simulation",
        module_title="Simulation",
        scope="project",
        group_id="simulation",
        group_title="Simulation",
        fields=[
            ConfigFieldDecl("simulation_enabled", "project", "boolean", False, False, "项目是否参与 Angelia 调度循环。", "project-runtime", ["gods/angelia/scheduler.py", "api/services/project_service.py"]),
            ConfigFieldDecl("simulation_interval_min", "project", "integer", 10, False, "调度最小间隔秒数。", "project-runtime", ["gods/angelia/policy.py"]),
            ConfigFieldDecl("simulation_interval_max", "project", "integer", 40, False, "调度最大间隔秒数。", "project-runtime", ["gods/angelia/policy.py"]),
        ],
    ),
    ConfigBlockDecl(
        module_id="pulse",
        module_title="Pulse",
        scope="project",
        group_id="pulse",
        group_title="Pulse",
        fields=[
            ConfigFieldDecl("pulse_event_inject_budget", "project", "integer", 3, False, "单轮脉冲注入事件预算。", "project-runtime", ["gods/angelia/pulse/policy.py"]),
            ConfigFieldDecl("pulse_interrupt_mode", "project", "string", "after_action", False, "脉冲中断模式。", "project-runtime", ["gods/angelia/pulse/policy.py"], enum=["after_action"]),
            ConfigFieldDecl("pulse_priority_weights", "project", "object", {"mail_event": 100, "manual": 80, "system": 60, "timer": 10}, False, "事件优先级权重。", "project-runtime", ["gods/angelia/policy.py", "gods/angelia/pulse/policy.py"]),
        ],
    ),
    ConfigBlockDecl(
        module_id="finalize",
        module_title="Finalize",
        scope="project",
        group_id="finalize",
        group_title="Finalize",
        fields=[
            ConfigFieldDecl("finalize_quiescent_enabled", "project", "boolean", True, False, "允许 finalize(quiescent) 让 agent 进入冷却。", "project-runtime", ["gods/angelia/policy.py", "gods/tools/comm_human.py"]),
            ConfigFieldDecl("finalize_sleep_min_sec", "project", "integer", 15, False, "quiescent 最小 sleep 秒数。", "project-runtime", ["gods/angelia/policy.py", "gods/tools/comm_human.py"]),
            ConfigFieldDecl("finalize_sleep_default_sec", "project", "integer", 120, False, "quiescent 默认 sleep 秒数。", "project-runtime", ["gods/angelia/policy.py", "gods/tools/comm_human.py"]),
            ConfigFieldDecl("finalize_sleep_max_sec", "project", "integer", 1800, False, "quiescent 最大 sleep 秒数。", "project-runtime", ["gods/angelia/policy.py", "gods/tools/comm_human.py"]),
        ],
    ),
]
