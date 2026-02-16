"""
Gods Platform - Runtime Configuration (Persistent)
"""
import os
import json
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from pathlib import Path

CONFIG_FILE = Path("config.json")

class AgentModelConfig(BaseModel):
    """
    Configuration for an agent's model settings.
    """
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
    """
    Configuration for a specific project, including agent settings and simulation controls.
    """
    name: Optional[str] = None
    active_agents: List[str] = ["genesis"]
    agent_settings: Dict[str, AgentModelConfig] = {
        "genesis": AgentModelConfig()
    }
    simulation_enabled: bool = False
    # 并行模式下每批最多同时触发的 Agent 数量
    autonomous_batch_size: int = 4
    simulation_interval_min: int = 10
    simulation_interval_max: int = 40
    # Event queue idle heartbeat (seconds) when no queued pulse exists.
    queue_idle_heartbeat_sec: int = 60
    # Max inbox events injected in one pulse.
    pulse_event_inject_budget: int = 3
    # Supported: after_action
    pulse_interrupt_mode: str = "after_action"
    # Priority weights by pulse event type.
    pulse_priority_weights: Dict[str, int] = Field(
        default_factory=lambda: {"inbox_event": 100, "manual": 80, "system": 60, "timer": 10}
    )
    # Master switch for event-driven inbox delivery.
    inbox_event_enabled: bool = True
    # Angelia event loop controls
    angelia_enabled: bool = True
    angelia_worker_per_agent: int = 1
    angelia_event_max_attempts: int = 3
    angelia_processing_timeout_sec: int = 60
    angelia_cooldown_preempt_types: List[str] = Field(default_factory=lambda: ["inbox_event", "manual"])
    angelia_timer_enabled: bool = True
    angelia_timer_idle_sec: int = 60
    angelia_dedupe_window_sec: int = 5
    summarize_threshold: int = 12
    summarize_keep_count: int = 5
    # Memory compression controls (full-read mode)
    memory_compact_trigger_chars: int = 200000
    memory_compact_keep_chars: int = 50000
    # Janus context strategy controls
    context_strategy: str = "structured_v1"
    context_token_budget_total: int = 32000
    context_budget_task_state: int = 4000
    context_budget_observations: int = 12000
    context_budget_inbox: int = 4000
    context_budget_inbox_unread: int = 2000
    context_budget_inbox_read_recent: int = 1000
    context_budget_inbox_receipts: int = 1000
    context_budget_recent_messages: int = 12000
    context_recent_message_limit: int = 50
    context_observation_window: int = 30
    context_include_inbox_status_hints: bool = True
    context_write_build_report: bool = True
    # Agent model<->tool loop cap per pulse
    tool_loop_max: int = 8
    # Phase-runtime controls
    phase_mode_enabled: bool = True
    # phase strategy: strict_triad | iterative_action
    phase_strategy: str = "strict_triad"
    # iterative_action strategy: max action-observe interactions per pulse
    phase_interaction_max: int = 3
    # stricter act-phase control
    phase_act_require_tool_call: bool = True
    phase_act_require_productive_tool: bool = True
    # require productive tool from this act index (1-based) in one pulse
    # e.g. 2 => first act can be diagnostic (read/list), from second act must be productive
    phase_act_productive_from_interaction: int = 2
    phase_repeat_limit: int = 2
    phase_explore_budget: int = 3
    phase_no_progress_limit: int = 3
    phase_single_tool_call: bool = True
    # Debug tracing
    debug_trace_enabled: bool = True
    debug_trace_max_events: int = 200
    debug_trace_full_content: bool = True
    # Full LLM IO tracing (request/response payload snapshots)
    debug_llm_trace_enabled: bool = True
    # Command execution governance
    command_max_parallel: int = 2
    command_timeout_sec: int = 60
    command_max_memory_mb: int = 512
    command_max_cpu_sec: int = 15
    command_max_output_chars: int = 4000
    # Command execution backend
    # docker | local
    command_executor: str = "docker"
    docker_enabled: bool = True
    docker_image: str = "gods-agent-base:py311"
    # bridge_local_only | none
    docker_network_mode: str = "bridge_local_only"
    docker_auto_start_on_project_start: bool = True
    docker_auto_stop_on_project_stop: bool = True
    docker_workspace_mount_mode: str = "agent_territory_rw"
    docker_readonly_rootfs: bool = False
    docker_extra_env: Dict[str, str] = Field(default_factory=dict)
    docker_cpu_limit: float = 1.0
    docker_memory_limit_mb: int = 512
    # Detach runtime governance
    detach_enabled: bool = True
    detach_max_running_per_agent: int = 2
    detach_max_running_per_project: int = 8
    detach_queue_max_per_agent: int = 8
    detach_ttl_sec: int = 1800
    detach_stop_grace_sec: int = 10
    detach_log_tail_chars: int = 4000
    # Hermes protocol bus controls
    hermes_enabled: bool = True
    hermes_default_timeout_sec: int = 30
    hermes_default_rate_per_minute: int = 60
    hermes_default_max_concurrency: int = 2
    # Security default: forbid direct agent_tool provider registration/invocation.
    hermes_allow_agent_tool_provider: bool = False

class SystemConfig(BaseModel):
    """
    Global system configuration, managing API keys and multiple projects.
    """
    openrouter_api_key: str = ""
    current_project: str = "default"
    # project_id -> project settings
    projects: Dict[str, ProjectConfig] = {
        "default": ProjectConfig(name="Default World")
    }

    def save(self):
        """
        Saves the current system configuration to the persistent config file.
        """
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=4))

    @classmethod
    def load(cls):
        """
        Loads the system configuration from the persistent config file, 
        performing migration from older formats if necessary.
        """
        if not CONFIG_FILE.exists():
            return cls()
        
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Migration logic: if 'projects' is missing, it's an old config
            if "projects" not in data:
                print("--- MIGRATING OLD CONFIG TO PROJECT STRUCTURE ---")
                old_active = data.get("active_agents", ["genesis"])
                old_settings = data.get("agent_settings", {"genesis": {}})
                
                # Create a default project with old settings
                default_proj = ProjectConfig(
                    name="Default World",
                    active_agents=old_active,
                    agent_settings={k: AgentModelConfig(**v) if isinstance(v, dict) else v for k, v in old_settings.items()},
                    simulation_enabled=data.get("simulation_enabled", False),
                    simulation_interval_min=data.get("simulation_interval_min", 10),
                    simulation_interval_max=data.get("simulation_interval_max", 40),
                    summarize_threshold=data.get("summarize_threshold", 12),
                    summarize_keep_count=data.get("summarize_keep_count", 5)
                )
                
                new_cfg = cls(
                    openrouter_api_key=data.get("openrouter_api_key", ""),
                    current_project="default",
                    projects={"default": default_proj}
                )
                new_cfg.save() # Save the migrated version
                return new_cfg
            
            return cls(**data)
        except Exception as e:
            print(f"Failed to load/migrate config: {e}")
            return cls()

def get_current_project() -> ProjectConfig:
    """
    Retrieves the configuration for the currently active project.
    """
    return runtime_config.projects.get(runtime_config.current_project, ProjectConfig(name="Safety", active_agents=[]))

def get_available_agents(project_id: str = None) -> List[str]:
    """
    Scans the project directory for available agent definitions.
    """
    if not project_id:
        project_id = runtime_config.current_project
        
    agents_dir = Path("projects") / project_id / "agents"
    if not agents_dir.exists():
        return []
    return [d.name for d in agents_dir.iterdir() if d.is_dir()]

# Global runtime instance (single initialization)
runtime_config = SystemConfig.load()
