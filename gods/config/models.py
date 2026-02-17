"""Typed config models for Gods runtime."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


CONFIG_FILE = Path("config.json")


def _default_projects() -> Dict[str, "ProjectConfig"]:
    return {"default": ProjectConfig(name="Default World")}


class AgentModelConfig(BaseModel):
    """Configuration for an agent's model settings."""
    model_config = ConfigDict(extra="forbid")

    model: str = "stepfun/step-3.5-flash:free"
    # Event-driven inbox is default path; check_inbox is opt-in for debug/audit.
    disabled_tools: List[str] = Field(default_factory=lambda: ["check_inbox"])
    # Optional agent-level phase runtime overrides (fallback to project defaults when None).
    phase_mode_enabled: Optional[bool] = None
    phase_strategy: Optional[str] = None
    # Optional agent-level context strategy overrides (fallback to project defaults when None).
    context_strategy: Optional[str] = None
    context_token_budget_total: Optional[int] = None


class ProjectConfig(BaseModel):
    """Project-level runtime configuration."""
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    active_agents: List[str] = Field(default_factory=list)
    agent_settings: Dict[str, AgentModelConfig] = Field(default_factory=dict)
    simulation_enabled: bool = False
    autonomous_batch_size: int = 4
    simulation_interval_min: int = 10
    simulation_interval_max: int = 40

    pulse_event_inject_budget: int = 3
    pulse_interrupt_mode: str = "after_action"
    pulse_priority_weights: Dict[str, int] = Field(
        default_factory=lambda: {"mail_event": 100, "manual": 80, "system": 60, "timer": 10}
    )

    angelia_enabled: bool = True
    angelia_worker_per_agent: int = 1
    angelia_event_max_attempts: int = 3
    angelia_processing_timeout_sec: int = 60
    angelia_cooldown_preempt_types: List[str] = Field(default_factory=lambda: ["mail_event", "manual"])
    angelia_timer_enabled: bool = True
    angelia_timer_idle_sec: int = 60
    angelia_dedupe_window_sec: int = 5

    summarize_threshold: int = 12
    summarize_keep_count: int = 5

    memory_compact_trigger_tokens: int = 12000
    memory_compact_strategy: str = "semantic_llm"

    context_strategy: str = "structured_v1"
    context_token_budget_total: int = 32000
    context_budget_task_state: int = 4000
    context_budget_observations: int = 12000
    context_budget_inbox: int = 4000
    context_budget_inbox_unread: int = 2000
    context_budget_inbox_read_recent: int = 1000
    context_budget_inbox_receipts: int = 1000
    context_budget_state_window: int = 12000
    context_state_window_limit: int = 50
    context_observation_window: int = 30
    context_include_inbox_status_hints: bool = True
    context_write_build_report: bool = True

    tool_loop_max: int = 8

    finalize_quiescent_enabled: bool = True
    finalize_sleep_min_sec: int = 15
    finalize_sleep_default_sec: int = 120
    finalize_sleep_max_sec: int = 1800

    phase_mode_enabled: bool = True
    phase_strategy: str = "strict_triad"
    phase_interaction_max: int = 3
    phase_act_require_tool_call: bool = True
    phase_act_require_productive_tool: bool = True
    phase_act_productive_from_interaction: int = 2
    phase_repeat_limit: int = 2
    phase_explore_budget: int = 3
    phase_no_progress_limit: int = 3
    phase_single_tool_call: bool = True

    debug_trace_enabled: bool = True
    debug_trace_max_events: int = 200
    debug_trace_full_content: bool = True
    debug_llm_trace_enabled: bool = True

    command_max_parallel: int = 2
    command_timeout_sec: int = 60
    command_max_memory_mb: int = 512
    command_max_cpu_sec: int = 15
    command_max_output_chars: int = 4000

    command_executor: str = "docker"
    docker_enabled: bool = True
    docker_image: str = "gods-agent-base:py311"
    docker_network_mode: str = "bridge_local_only"
    docker_auto_start_on_project_start: bool = True
    docker_auto_stop_on_project_stop: bool = True
    docker_workspace_mount_mode: str = "agent_territory_rw"
    docker_readonly_rootfs: bool = False
    docker_extra_env: Dict[str, str] = Field(default_factory=dict)
    docker_cpu_limit: float = 1.0
    docker_memory_limit_mb: int = 512

    detach_enabled: bool = True
    detach_max_running_per_agent: int = 2
    detach_max_running_per_project: int = 8
    detach_queue_max_per_agent: int = 8
    detach_ttl_sec: int = 1800
    detach_stop_grace_sec: int = 10
    detach_log_tail_chars: int = 4000

    hermes_enabled: bool = True
    hermes_default_timeout_sec: int = 30
    hermes_default_rate_per_minute: int = 60
    hermes_default_max_concurrency: int = 2
    hermes_allow_agent_tool_provider: bool = False


class SystemConfig(BaseModel):
    """Global system configuration and project map."""
    model_config = ConfigDict(extra="forbid")

    openrouter_api_key: str = ""
    current_project: str = "default"
    projects: Dict[str, ProjectConfig] = Field(default_factory=_default_projects)

    def save(self):
        from gods.config.loader import save_system_config

        save_system_config(self)

    @classmethod
    def load(cls):
        from gods.config.loader import load_system_config

        return load_system_config()
