"""Typed config models for Gods runtime."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict

from gods.config.blocks import AGENT_DEFAULTS, PROJECT_DEFAULTS, SYSTEM_DEFAULTS


CONFIG_FILE = Path("config.json")


def _deepcopy_default(v):
    return copy.deepcopy(v)


def _default_projects() -> Dict[str, "ProjectConfig"]:
    raw = _deepcopy_default(SYSTEM_DEFAULTS.get("projects", {}))
    if not isinstance(raw, dict) or not raw:
        raw = {"default": {"name": "Default World"}}
    out: Dict[str, ProjectConfig] = {}
    for pid, pdata in raw.items():
        if isinstance(pdata, dict):
            out[str(pid)] = ProjectConfig(**pdata)
    if "default" not in out:
        out["default"] = ProjectConfig(name="Default World")
    return out


class AgentModelConfig(BaseModel):
    """Configuration for an agent's model settings."""

    model_config = ConfigDict(extra="forbid")

    model: str = AGENT_DEFAULTS["model"]
    disabled_tools: List[str] = Field(default_factory=lambda: _deepcopy_default(AGENT_DEFAULTS["disabled_tools"]))
    phase_strategy: Optional[str] = AGENT_DEFAULTS["phase_strategy"]
    context_strategy: Optional[str] = AGENT_DEFAULTS["context_strategy"]
    context_token_budget_total: Optional[int] = AGENT_DEFAULTS["context_token_budget_total"]
    metis_refresh_mode: Optional[str] = AGENT_DEFAULTS["metis_refresh_mode"]
    tool_policies: Dict[str, Dict[str, List[str]]] = Field(
        default_factory=lambda: _deepcopy_default(AGENT_DEFAULTS["tool_policies"])
    )


class ProjectConfig(BaseModel):
    """Project-level runtime configuration."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = PROJECT_DEFAULTS["name"]
    active_agents: List[str] = Field(default_factory=lambda: _deepcopy_default(PROJECT_DEFAULTS["active_agents"]))
    agent_settings: Dict[str, AgentModelConfig] = Field(
        default_factory=lambda: _deepcopy_default(PROJECT_DEFAULTS["agent_settings"])
    )
    simulation_enabled: bool = PROJECT_DEFAULTS["simulation_enabled"]
    autonomous_batch_size: int = PROJECT_DEFAULTS["autonomous_batch_size"]
    simulation_interval_min: int = PROJECT_DEFAULTS["simulation_interval_min"]
    simulation_interval_max: int = PROJECT_DEFAULTS["simulation_interval_max"]

    pulse_event_inject_budget: int = PROJECT_DEFAULTS["pulse_event_inject_budget"]
    pulse_interrupt_mode: str = PROJECT_DEFAULTS["pulse_interrupt_mode"]
    pulse_priority_weights: Dict[str, int] = Field(
        default_factory=lambda: _deepcopy_default(PROJECT_DEFAULTS["pulse_priority_weights"])
    )

    angelia_enabled: bool = PROJECT_DEFAULTS["angelia_enabled"]
    angelia_worker_per_agent: int = PROJECT_DEFAULTS["angelia_worker_per_agent"]
    angelia_event_max_attempts: int = PROJECT_DEFAULTS["angelia_event_max_attempts"]
    angelia_processing_timeout_sec: int = PROJECT_DEFAULTS["angelia_processing_timeout_sec"]
    angelia_pick_batch_size: int = PROJECT_DEFAULTS["angelia_pick_batch_size"]
    angelia_cooldown_preempt_types: List[str] = Field(
        default_factory=lambda: _deepcopy_default(PROJECT_DEFAULTS["angelia_cooldown_preempt_types"])
    )
    angelia_timer_enabled: bool = PROJECT_DEFAULTS["angelia_timer_enabled"]
    angelia_timer_idle_sec: int = PROJECT_DEFAULTS["angelia_timer_idle_sec"]
    angelia_dedupe_window_sec: int = PROJECT_DEFAULTS["angelia_dedupe_window_sec"]

    summarize_threshold: int = PROJECT_DEFAULTS["summarize_threshold"]
    summarize_keep_count: int = PROJECT_DEFAULTS["summarize_keep_count"]

    memory_compact_trigger_tokens: int = PROJECT_DEFAULTS["memory_compact_trigger_tokens"]
    memory_compact_strategy: str = PROJECT_DEFAULTS["memory_compact_strategy"]

    context_strategy: str = PROJECT_DEFAULTS["context_strategy"]
    context_token_budget_total: int = PROJECT_DEFAULTS["context_token_budget_total"]
    context_budget_task_state: int = PROJECT_DEFAULTS["context_budget_task_state"]

    context_budget_inbox: int = PROJECT_DEFAULTS["context_budget_inbox"]
    context_budget_inbox_unread: int = PROJECT_DEFAULTS["context_budget_inbox_unread"]
    context_budget_inbox_read_recent: int = PROJECT_DEFAULTS["context_budget_inbox_read_recent"]
    context_budget_inbox_receipts: int = PROJECT_DEFAULTS["context_budget_inbox_receipts"]
    context_short_window_intents: int = PROJECT_DEFAULTS["context_short_window_intents"]
    context_n_recent: int = PROJECT_DEFAULTS["context_n_recent"]
    context_recent_token_budget: int = PROJECT_DEFAULTS["context_recent_token_budget"]
    context_token_budget_chronicle_trigger: int = PROJECT_DEFAULTS["context_token_budget_chronicle_trigger"]

    context_include_inbox_status_hints: bool = PROJECT_DEFAULTS["context_include_inbox_status_hints"]
    context_write_build_report: bool = PROJECT_DEFAULTS["context_write_build_report"]
    metis_refresh_mode: str = PROJECT_DEFAULTS["metis_refresh_mode"]

    tool_loop_max: int = PROJECT_DEFAULTS["tool_loop_max"]
    tool_policies: Dict[str, Dict[str, List[str]]] = Field(
        default_factory=lambda: _deepcopy_default(PROJECT_DEFAULTS["tool_policies"])
    )

    finalize_quiescent_enabled: bool = PROJECT_DEFAULTS["finalize_quiescent_enabled"]
    finalize_sleep_min_sec: int = PROJECT_DEFAULTS["finalize_sleep_min_sec"]
    finalize_sleep_default_sec: int = PROJECT_DEFAULTS["finalize_sleep_default_sec"]
    finalize_sleep_max_sec: int = PROJECT_DEFAULTS["finalize_sleep_max_sec"]

    phase_strategy: str = PROJECT_DEFAULTS["phase_strategy"]

    debug_trace_enabled: bool = PROJECT_DEFAULTS["debug_trace_enabled"]
    debug_trace_max_events: int = PROJECT_DEFAULTS["debug_trace_max_events"]
    debug_trace_full_content: bool = PROJECT_DEFAULTS["debug_trace_full_content"]
    debug_llm_trace_enabled: bool = PROJECT_DEFAULTS["debug_llm_trace_enabled"]
    llm_control_enabled: bool = PROJECT_DEFAULTS["llm_control_enabled"]
    llm_global_max_concurrency: int = PROJECT_DEFAULTS["llm_global_max_concurrency"]
    llm_global_rate_per_minute: int = PROJECT_DEFAULTS["llm_global_rate_per_minute"]
    llm_project_max_concurrency: int = PROJECT_DEFAULTS["llm_project_max_concurrency"]
    llm_project_rate_per_minute: int = PROJECT_DEFAULTS["llm_project_rate_per_minute"]
    llm_acquire_timeout_sec: int = PROJECT_DEFAULTS["llm_acquire_timeout_sec"]
    llm_request_timeout_sec: int = PROJECT_DEFAULTS["llm_request_timeout_sec"]
    llm_retry_interval_ms: int = PROJECT_DEFAULTS["llm_retry_interval_ms"]

    command_max_parallel: int = PROJECT_DEFAULTS["command_max_parallel"]
    command_timeout_sec: int = PROJECT_DEFAULTS["command_timeout_sec"]
    command_max_memory_mb: int = PROJECT_DEFAULTS["command_max_memory_mb"]
    command_max_cpu_sec: int = PROJECT_DEFAULTS["command_max_cpu_sec"]
    command_max_output_chars: int = PROJECT_DEFAULTS["command_max_output_chars"]

    command_executor: str = PROJECT_DEFAULTS["command_executor"]
    docker_enabled: bool = PROJECT_DEFAULTS["docker_enabled"]
    docker_image: str = PROJECT_DEFAULTS["docker_image"]
    docker_network_mode: str = PROJECT_DEFAULTS["docker_network_mode"]
    docker_auto_start_on_project_start: bool = PROJECT_DEFAULTS["docker_auto_start_on_project_start"]
    docker_auto_stop_on_project_stop: bool = PROJECT_DEFAULTS["docker_auto_stop_on_project_stop"]
    docker_workspace_mount_mode: str = PROJECT_DEFAULTS["docker_workspace_mount_mode"]
    docker_readonly_rootfs: bool = PROJECT_DEFAULTS["docker_readonly_rootfs"]
    docker_extra_env: Dict[str, str] = Field(default_factory=lambda: _deepcopy_default(PROJECT_DEFAULTS["docker_extra_env"]))
    docker_cpu_limit: float = PROJECT_DEFAULTS["docker_cpu_limit"]
    docker_memory_limit_mb: int = PROJECT_DEFAULTS["docker_memory_limit_mb"]

    detach_enabled: bool = PROJECT_DEFAULTS["detach_enabled"]
    detach_max_running_per_agent: int = PROJECT_DEFAULTS["detach_max_running_per_agent"]
    detach_max_running_per_project: int = PROJECT_DEFAULTS["detach_max_running_per_project"]
    detach_queue_max_per_agent: int = PROJECT_DEFAULTS["detach_queue_max_per_agent"]
    detach_ttl_sec: int = PROJECT_DEFAULTS["detach_ttl_sec"]
    detach_stop_grace_sec: int = PROJECT_DEFAULTS["detach_stop_grace_sec"]
    detach_log_tail_chars: int = PROJECT_DEFAULTS["detach_log_tail_chars"]

    hermes_enabled: bool = PROJECT_DEFAULTS["hermes_enabled"]
    hermes_default_timeout_sec: int = PROJECT_DEFAULTS["hermes_default_timeout_sec"]
    hermes_default_rate_per_minute: int = PROJECT_DEFAULTS["hermes_default_rate_per_minute"]
    hermes_default_max_concurrency: int = PROJECT_DEFAULTS["hermes_default_max_concurrency"]
    hermes_allow_agent_tool_provider: bool = PROJECT_DEFAULTS["hermes_allow_agent_tool_provider"]


class SystemConfig(BaseModel):
    """Global system configuration and project map."""

    model_config = ConfigDict(extra="forbid")

    openrouter_api_key: str = SYSTEM_DEFAULTS["openrouter_api_key"]
    current_project: str = SYSTEM_DEFAULTS["current_project"]
    projects: Dict[str, ProjectConfig] = Field(default_factory=_default_projects)

    def save(self):
        from gods.config.loader import save_system_config

        save_system_config(self)

    @classmethod
    def load(cls):
        from gods.config.loader import load_system_config

        return load_system_config()
