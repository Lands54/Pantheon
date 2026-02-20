"""Registry catalog for config fields and declarative metadata."""
from __future__ import annotations

from typing import Any, get_args, get_origin

from gods.metis.strategy_specs import export_strategy_default_tools, export_strategy_phase_map
from gods.config.models import AgentModelConfig, ProjectConfig, SystemConfig
from gods.config.registry import ConfigEntry, ConfigRegistry


_DEPRECATED_PROJECT_KEYS = {
    "autonomous_batch_size",
    "angelia_worker_per_agent",
    "summarize_threshold",
    "summarize_keep_count",
    "docker_workspace_mount_mode",
    "hermes_enabled",
    "hermes_default_timeout_sec",
    "hermes_default_rate_per_minute",
    "hermes_default_max_concurrency",
}
_DEPRECATED_AGENT_KEYS: set[str] = set()

_PROJECT_ENUMS: dict[str, list[str]] = {
    "phase_strategy": ["react_graph", "freeform"],
    "context_strategy": ["sequential_v1"],
    "memory_compact_strategy": ["semantic_llm", "rule_based"],
    "command_executor": ["docker", "local"],
    "docker_network_mode": ["bridge_local_only", "none"],
    "pulse_interrupt_mode": ["after_action"],
    "metis_refresh_mode": ["pulse", "node"],
}

_PROJECT_CONSTRAINTS: dict[str, dict[str, Any]] = {
    "tool_loop_max": {"min": 1, "max": 64},
    "context_token_budget_total": {"min": 4000, "max": 256000},
    "context_n_recent": {"min": 1, "max": 5000},
    "context_recent_token_budget": {"min": 0, "max": 256000},
    "context_token_budget_chronicle_trigger": {"min": 1000, "max": 512000},
    "llm_global_max_concurrency": {"min": 1, "max": 256},
    "llm_global_rate_per_minute": {"min": 1, "max": 200000},
    "llm_project_max_concurrency": {"min": 1, "max": 256},
    "llm_project_rate_per_minute": {"min": 1, "max": 200000},
    "llm_acquire_timeout_sec": {"min": 1, "max": 300},
    "llm_retry_interval_ms": {"min": 10, "max": 5000},
}

_PROJECT_RUNTIME: dict[str, list[str]] = {
    "simulation_enabled": ["gods/angelia/scheduler.py", "api/services/project_service.py"],
    "simulation_interval_min": ["gods/angelia/policy.py"],
    "simulation_interval_max": ["gods/angelia/policy.py"],
    "pulse_event_inject_budget": ["gods/angelia/pulse/policy.py"],
    "pulse_interrupt_mode": ["gods/angelia/pulse/policy.py"],
    "pulse_priority_weights": ["gods/angelia/policy.py", "gods/angelia/pulse/policy.py"],
    "angelia_enabled": ["gods/angelia/scheduler.py"],
    "angelia_event_max_attempts": ["gods/angelia/policy.py"],
    "angelia_processing_timeout_sec": ["gods/angelia/policy.py"],
    "angelia_cooldown_preempt_types": ["gods/angelia/policy.py"],
    "angelia_timer_enabled": ["gods/angelia/policy.py"],
    "angelia_timer_idle_sec": ["gods/angelia/policy.py", "gods/angelia/pulse/policy.py"],
    "angelia_dedupe_window_sec": ["gods/angelia/policy.py"],
    "memory_compact_trigger_tokens": ["gods/mnemosyne/compaction.py"],
    "memory_compact_strategy": ["gods/mnemosyne/compaction.py"],
    "context_strategy": ["gods/janus/context_policy.py"],
    "context_token_budget_total": ["gods/janus/context_policy.py"],
    "context_budget_task_state": ["gods/janus/context_policy.py"],

    "context_budget_inbox": ["gods/janus/context_policy.py"],
    "context_budget_inbox_unread": ["gods/janus/context_policy.py"],
    "context_budget_inbox_read_recent": ["gods/janus/context_policy.py"],
    "context_budget_inbox_receipts": ["gods/janus/context_policy.py"],
    "context_short_window_intents": ["gods/janus/context_policy.py", "gods/mnemosyne/janus_snapshot.py"],
    "context_n_recent": ["gods/janus/context_policy.py", "gods/janus/strategies/sequential_v1.py"],
    "context_recent_token_budget": ["gods/janus/context_policy.py", "gods/janus/strategies/sequential_v1.py"],
    "context_token_budget_chronicle_trigger": ["gods/janus/context_policy.py", "gods/janus/strategies/sequential_v1.py"],

    "context_include_inbox_status_hints": ["gods/janus/context_policy.py"],
    "context_write_build_report": ["gods/janus/context_policy.py"],
    "metis_refresh_mode": ["gods/metis/snapshot.py", "gods/metis/strategy_runtime.py"],
    "tool_loop_max": ["gods/agents/runtime/engine.py"],
    "tool_policies": ["gods/agents/base.py"],
    "finalize_quiescent_enabled": ["gods/angelia/policy.py", "gods/tools/comm_human.py"],
    "finalize_sleep_min_sec": ["gods/angelia/policy.py", "gods/tools/comm_human.py"],
    "finalize_sleep_default_sec": ["gods/angelia/policy.py", "gods/tools/comm_human.py"],
    "finalize_sleep_max_sec": ["gods/angelia/policy.py", "gods/tools/comm_human.py"],
    "phase_strategy": ["gods/agents/runtime/engine.py", "cli/commands/agent.py"],
    "debug_trace_enabled": ["gods/agents/debug_trace.py"],
    "debug_trace_max_events": ["gods/agents/debug_trace.py"],
    "debug_trace_full_content": ["gods/agents/debug_trace.py"],
    "debug_llm_trace_enabled": ["gods/agents/brain.py"],
    "llm_control_enabled": ["gods/agents/llm_control.py", "gods/agents/brain.py"],
    "llm_global_max_concurrency": ["gods/agents/llm_control.py"],
    "llm_global_rate_per_minute": ["gods/agents/llm_control.py"],
    "llm_project_max_concurrency": ["gods/agents/llm_control.py"],
    "llm_project_rate_per_minute": ["gods/agents/llm_control.py"],
    "llm_acquire_timeout_sec": ["gods/agents/llm_control.py"],
    "llm_retry_interval_ms": ["gods/agents/llm_control.py"],
    "command_max_parallel": ["gods/tools/execution.py"],
    "command_timeout_sec": ["gods/tools/execution.py"],
    "command_max_memory_mb": ["gods/tools/execution.py"],
    "command_max_cpu_sec": ["gods/tools/execution.py"],
    "command_max_output_chars": ["gods/tools/execution.py"],
    "command_executor": ["api/services/project_service.py"],
    "docker_enabled": ["api/services/project_service.py", "api/services/simulation_service.py"],
    "docker_image": ["gods/runtime/docker/manager.py"],
    "docker_network_mode": ["gods/runtime/docker/manager.py"],
    "docker_auto_start_on_project_start": ["api/services/project_service.py"],
    "docker_auto_stop_on_project_stop": ["api/services/project_service.py"],
    "docker_readonly_rootfs": ["gods/runtime/docker/manager.py"],
    "docker_extra_env": ["gods/runtime/docker/manager.py"],
    "docker_cpu_limit": ["gods/runtime/docker/manager.py"],
    "docker_memory_limit_mb": ["gods/runtime/docker/manager.py"],
    "detach_enabled": ["gods/runtime/detach/service.py"],
    "detach_max_running_per_agent": ["gods/runtime/detach/service.py"],
    "detach_max_running_per_project": ["gods/runtime/detach/service.py"],
    "detach_queue_max_per_agent": ["gods/runtime/detach/service.py"],
    "detach_ttl_sec": ["gods/runtime/detach/service.py"],
    "detach_stop_grace_sec": ["gods/runtime/detach/service.py"],
    "detach_log_tail_chars": ["gods/runtime/detach/service.py"],
    "hermes_allow_agent_tool_provider": ["gods/hermes/policy.py", "api/services/hermes_service.py"],
    "active_agents": ["api/services/project_service.py", "api/services/angelia_service.py"],
    "agent_settings": ["gods/agents/base.py", "gods/agents/brain.py"],
    "name": ["api/services/project_service.py"],
}

_AGENT_RUNTIME: dict[str, list[str]] = {
    "model": ["gods/agents/brain.py"],
    "disabled_tools": ["gods/agents/base.py", "gods/agents/tool_policy.py"],
    "phase_strategy": ["gods/agents/runtime/engine.py"],
    "context_strategy": ["gods/janus/context_policy.py"],
    "context_token_budget_total": ["gods/janus/context_policy.py"],
    "metis_refresh_mode": ["gods/metis/snapshot.py"],
    "tool_policies": ["gods/agents/base.py"],
}

_SYSTEM_RUNTIME: dict[str, list[str]] = {
    "openrouter_api_key": ["gods/agents/brain.py", "api/services/config_service.py"],
    "current_project": ["gods/config/runtime.py", "api/services/project_service.py"],
    "projects": ["gods/config/runtime.py", "gods/config/loader.py"],
}

_PROJECT_DESCRIPTIONS: dict[str, str] = {
    "simulation_enabled": "项目是否参与 Angelia 调度循环。",
    "simulation_interval_min": "调度最小间隔秒数。",
    "simulation_interval_max": "调度最大间隔秒数。",
    "autonomous_batch_size": "历史批量脉冲参数，当前保留为兼容阅读。",
    "agent_settings": "按 agent_id 的运行覆盖配置。",
    "tool_policies": "项目级策略/阶段工具白名单（推荐主路径）。",
    "tool_loop_max": "单次脉冲工具调用上限。",
    "context_n_recent": "顺序上下文中作为 recent 保留的卡片数量。",
    "context_recent_token_budget": "顺序上下文 recent 区段的 token 预算（>0 时按预算截取；<=0 时退回按 context_n_recent）。",
    "context_token_budget_chronicle_trigger": "chronicle 区段超过该估算 token 时触发压缩。",
    "metis_refresh_mode": "Metis envelope 刷新模式：pulse(每轮一次) 或 node(每节点增量刷新)。",
    "llm_control_enabled": "启用 LLM 全局/项目级限速与并发控制。",
    "llm_global_max_concurrency": "LLM 全局并发上限（跨所有项目与 agent）。",
    "llm_global_rate_per_minute": "LLM 全局每分钟请求上限（RPM）。",
    "llm_project_max_concurrency": "LLM 单项目并发上限。",
    "llm_project_rate_per_minute": "LLM 单项目每分钟请求上限（RPM）。",
    "llm_acquire_timeout_sec": "请求被限流时等待许可的超时时间（秒）。",
    "llm_retry_interval_ms": "限流重试轮询间隔（毫秒）。",
}

_AGENT_DESCRIPTIONS: dict[str, str] = {
    "disabled_tools": "该 agent 禁用工具列表。",
    "tool_policies": "该 agent 的策略/阶段工具白名单覆盖。",
    "metis_refresh_mode": "该 agent 的 Metis 刷新模式覆盖（pulse|node）。",
}

_SYSTEM_DESCRIPTIONS: dict[str, str] = {
    "openrouter_api_key": "OpenRouter API Key。保存时会脱敏回显。",
    "current_project": "当前激活项目 ID。",
    "projects": "项目配置映射。",
}

_GROUPS = [
    {"id": "simulation", "title": "Simulation", "scope": "project", "keys": ["simulation_enabled", "autonomous_batch_size", "simulation_interval_min", "simulation_interval_max"]},
    {"id": "pulse", "title": "Pulse", "scope": "project", "keys": ["pulse_event_inject_budget", "pulse_interrupt_mode", "pulse_priority_weights"]},
    {"id": "angelia", "title": "Angelia", "scope": "project", "keys": ["angelia_enabled", "angelia_worker_per_agent", "angelia_event_max_attempts", "angelia_processing_timeout_sec", "angelia_cooldown_preempt_types", "angelia_timer_enabled", "angelia_timer_idle_sec", "angelia_dedupe_window_sec"]},
    {"id": "memory", "title": "Memory", "scope": "project", "keys": ["summarize_threshold", "summarize_keep_count", "memory_compact_trigger_tokens", "memory_compact_strategy"]},
    {"id": "context", "title": "Context", "scope": "project", "keys": ["context_strategy", "context_token_budget_total", "context_budget_task_state", "context_budget_inbox", "context_budget_inbox_unread", "context_budget_inbox_read_recent", "context_budget_inbox_receipts", "context_short_window_intents", "context_n_recent", "context_recent_token_budget", "context_token_budget_chronicle_trigger", "context_include_inbox_status_hints", "context_write_build_report", "metis_refresh_mode"]},
    {"id": "runtime", "title": "Runtime", "scope": "project", "keys": ["command_executor", "command_max_parallel", "command_timeout_sec", "command_max_memory_mb", "command_max_cpu_sec", "command_max_output_chars", "docker_enabled", "docker_image", "docker_network_mode", "docker_auto_start_on_project_start", "docker_auto_stop_on_project_stop", "docker_workspace_mount_mode", "docker_readonly_rootfs", "docker_extra_env", "docker_cpu_limit", "docker_memory_limit_mb", "detach_enabled", "detach_max_running_per_agent", "detach_max_running_per_project", "detach_queue_max_per_agent", "detach_ttl_sec", "detach_stop_grace_sec", "detach_log_tail_chars", "llm_control_enabled", "llm_global_max_concurrency", "llm_global_rate_per_minute", "llm_project_max_concurrency", "llm_project_rate_per_minute", "llm_acquire_timeout_sec", "llm_retry_interval_ms"]},
    {"id": "tools", "title": "Tools", "scope": "project", "keys": ["tool_loop_max", "tool_policies", "agent_settings", "hermes_enabled", "hermes_default_timeout_sec", "hermes_default_rate_per_minute", "hermes_default_max_concurrency", "hermes_allow_agent_tool_provider"]},
    {"id": "debug", "title": "Debug", "scope": "project", "keys": ["debug_trace_enabled", "debug_trace_max_events", "debug_trace_full_content", "debug_llm_trace_enabled"]},
    {"id": "finalize", "title": "Finalize", "scope": "project", "keys": ["finalize_quiescent_enabled", "finalize_sleep_min_sec", "finalize_sleep_default_sec", "finalize_sleep_max_sec"]},
    {"id": "agent", "title": "Agent Overrides", "scope": "agent", "keys": ["model", "phase_strategy", "context_strategy", "context_token_budget_total", "metis_refresh_mode", "disabled_tools", "tool_policies"], "default_collapsed": True},
]

_STRATEGY_PHASES = export_strategy_phase_map()
_RUNTIME_NODE_DEFAULT_TOOLS = export_strategy_default_tools()


def _infer_type_and_nullable(annotation: Any) -> tuple[str, bool]:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is None:
        if annotation is bool:
            return "boolean", False
        if annotation is int:
            return "integer", False
        if annotation is float:
            return "number", False
        if annotation is str:
            return "string", False
        if annotation is dict:
            return "object", False
        if annotation is list:
            return "array", False
        return "object", False

    if origin in {list, tuple, set}:
        return "array", False
    if origin in {dict}:
        return "object", False

    if str(origin).endswith("Union") and args:
        non_null = [a for a in args if str(a) != "<class 'NoneType'>"]
        nullable = len(non_null) != len(args)
        if len(non_null) == 1:
            t, _ = _infer_type_and_nullable(non_null[0])
            return t, nullable
        return "object", nullable

    return "object", False


def _entry_from_model(scope: str, key: str, model_field: Any, *, description: str, owner: str, runtime_used_by: list[str], status: str = "active", enum: list[str] | None = None, constraints: dict[str, Any] | None = None, ui: dict[str, Any] | None = None) -> ConfigEntry:
    f_type, nullable = _infer_type_and_nullable(model_field.annotation)
    default = None
    if model_field.default is not None:
        default = model_field.default
    elif getattr(model_field, "default_factory", None):
        try:
            default = model_field.default_factory()
        except Exception:
            default = None

    return ConfigEntry(
        key=key,
        scope=scope,
        type=f_type,
        nullable=nullable,
        default=default,
        description=description,
        owner=owner,
        runtime_used_by=runtime_used_by,
        status=status,
        enum=enum,
        constraints=constraints,
        ui=ui,
    )


def build_registry() -> ConfigRegistry:
    system_entries: list[ConfigEntry] = []
    for key, mf in SystemConfig.model_fields.items():
        system_entries.append(
            _entry_from_model(
                "system",
                key,
                mf,
                description=_SYSTEM_DESCRIPTIONS.get(key, f"系统配置项：{key}"),
                owner="core-runtime",
                runtime_used_by=_SYSTEM_RUNTIME.get(key, ["unknown (audit required)"]),
            )
        )

    project_entries: list[ConfigEntry] = []
    for key, mf in ProjectConfig.model_fields.items():
        project_entries.append(
            _entry_from_model(
                "project",
                key,
                mf,
                description=_PROJECT_DESCRIPTIONS.get(key, f"项目配置项：{key}"),
                owner="project-runtime",
                runtime_used_by=_PROJECT_RUNTIME.get(key, [] if key in _DEPRECATED_PROJECT_KEYS else ["unknown (audit required)"]),
                status="deprecated" if key in _DEPRECATED_PROJECT_KEYS else "active",
                enum=_PROJECT_ENUMS.get(key),
                constraints=_PROJECT_CONSTRAINTS.get(key),
                ui=(
                    {
                        "widget": "strategy_phase_tool_allowlist",
                        "strategy_phases": _STRATEGY_PHASES,
                        "strategy_default_tools": _RUNTIME_NODE_DEFAULT_TOOLS,
                        "fixed_phases": True,
                        "spec_source": "gods.metis.strategy_specs",
                    }
                    if key == "tool_policies"
                    else None
                ),
            )
        )

    agent_entries: list[ConfigEntry] = []
    for key, mf in AgentModelConfig.model_fields.items():
        agent_entries.append(
            _entry_from_model(
                "agent",
                key,
                mf,
                description=_AGENT_DESCRIPTIONS.get(key, f"Agent 覆盖配置：{key}"),
                owner="agent-runtime",
                runtime_used_by=_AGENT_RUNTIME.get(key, [] if key in _DEPRECATED_AGENT_KEYS else ["unknown (audit required)"]),
                status="deprecated" if key in _DEPRECATED_AGENT_KEYS else "active",
                enum=["react_graph", "freeform"] if key == "phase_strategy" else (["sequential_v1"] if key == "context_strategy" else (["pulse", "node"] if key == "metis_refresh_mode" else None)),
                ui=(
                    {
                        "widget": "strategy_phase_tool_allowlist",
                        "strategy_phases": _STRATEGY_PHASES,
                        "strategy_default_tools": _RUNTIME_NODE_DEFAULT_TOOLS,
                        "fixed_phases": True,
                        "spec_source": "gods.metis.strategy_specs",
                    }
                    if key == "tool_policies"
                    else None
                ),
            )
        )

    return ConfigRegistry(
        version="1.0.0",
        fields={
            "system": system_entries,
            "project": project_entries,
            "agent": agent_entries,
        },
        groups=_GROUPS,
    )


CONFIG_REGISTRY = build_registry()
