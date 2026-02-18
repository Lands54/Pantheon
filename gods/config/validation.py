"""Runtime config normalization and safety guards."""
from __future__ import annotations

import logging
import re

from gods.config.models import ProjectConfig, SystemConfig
from gods.identity import is_valid_agent_id

logger = logging.getLogger("GodsConfig")

_ALLOWED_PHASE_STRATEGIES = {"react_graph", "freeform"}
_ALLOWED_CONTEXT_STRATEGIES = {"structured_v1"}
_ALLOWED_COMPACT_STRATEGIES = {"semantic_llm", "rule_based"}
_ALLOWED_EXECUTORS = {"docker", "local"}
_ALLOWED_DOCKER_NET = {"bridge_local_only", "none"}
_ALLOWED_PULSE_INTERRUPT = {"after_action"}
_ALLOWED_TOOL_HINTS = {"mail_event", "manual", "system", "timer"}
_ALLOWED_METIS_REFRESH_MODE = {"pulse", "node"}
_STRATEGY_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_PHASE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _clamp_float(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _fallback_str(raw: str, allowed: set[str], default: str, field: str, project_id: str) -> str:
    v = str(raw or "").strip().lower()
    if v in allowed:
        return v
    logger.warning("Invalid %s='%s' in project '%s', fallback to '%s'", field, raw, project_id, default)
    return default


def _require_allowed_str(raw: str, allowed: set[str], field: str, project_id: str) -> str:
    v = str(raw or "").strip().lower()
    if v in allowed:
        return v
    raise ValueError(
        f"invalid {field}='{raw}' in project '{project_id}', allowed: {', '.join(sorted(allowed))}"
    )


def _normalize_tool_policies(
    raw: dict | None,
    *,
    project_id: str,
    owner: str,
    known_tools: set[str],
) -> dict[str, dict[str, list[str]]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"invalid {owner}.tool_policies in project '{project_id}': must be object")
    out: dict[str, dict[str, list[str]]] = {}
    for strategy_name, phase_map in raw.items():
        strategy = str(strategy_name or "").strip()
        if not _STRATEGY_NAME_RE.match(strategy):
            raise ValueError(
                f"invalid {owner}.tool_policies strategy '{strategy}' in project '{project_id}': "
                "must match ^[a-z][a-z0-9_]{0,63}$"
            )
        if not isinstance(phase_map, dict):
            raise ValueError(
                f"invalid {owner}.tool_policies.{strategy} in project '{project_id}': must be object"
            )
        phases: dict[str, list[str]] = {}
        for phase_name, tools in phase_map.items():
            phase = str(phase_name or "").strip()
            if not _PHASE_NAME_RE.match(phase):
                raise ValueError(
                    f"invalid {owner}.tool_policies.{strategy} phase '{phase}' in project '{project_id}': "
                    "must match ^[a-z][a-z0-9_]{0,63}$"
                )
            if not isinstance(tools, list):
                raise ValueError(
                    f"invalid {owner}.tool_policies.{strategy}.{phase} in project '{project_id}': "
                    "must be array of tool names"
                )
            seen: set[str] = set()
            normalized: list[str] = []
            for item in tools:
                tn = str(item or "").strip()
                if not tn:
                    continue
                if tn not in known_tools:
                    raise ValueError(
                        f"invalid {owner}.tool_policies.{strategy}.{phase} tool '{tn}' in "
                        f"project '{project_id}': unknown tool"
                    )
                if tn in seen:
                    continue
                seen.add(tn)
                normalized.append(tn)
            phases[phase] = normalized
        out[strategy] = phases
    return out


def normalize_project_config(project_id: str, proj: ProjectConfig) -> ProjectConfig:
    from gods.tools import available_tool_names

    known_tools = set(available_tool_names())

    proj.phase_strategy = _require_allowed_str(proj.phase_strategy, _ALLOWED_PHASE_STRATEGIES, "phase_strategy", project_id)
    proj.context_strategy = _fallback_str(
        proj.context_strategy,
        _ALLOWED_CONTEXT_STRATEGIES,
        "structured_v1",
        "context_strategy",
        project_id,
    )
    proj.memory_compact_strategy = _fallback_str(
        proj.memory_compact_strategy,
        _ALLOWED_COMPACT_STRATEGIES,
        "semantic_llm",
        "memory_compact_strategy",
        project_id,
    )
    proj.command_executor = _fallback_str(proj.command_executor, _ALLOWED_EXECUTORS, "local", "command_executor", project_id)
    proj.docker_network_mode = _fallback_str(
        proj.docker_network_mode,
        _ALLOWED_DOCKER_NET,
        "bridge_local_only",
        "docker_network_mode",
        project_id,
    )
    proj.pulse_interrupt_mode = _fallback_str(
        proj.pulse_interrupt_mode,
        _ALLOWED_PULSE_INTERRUPT,
        "after_action",
        "pulse_interrupt_mode",
        project_id,
    )

    proj.autonomous_batch_size = _clamp_int(proj.autonomous_batch_size, 1, 64)
    proj.simulation_interval_min = _clamp_int(proj.simulation_interval_min, 1, 600)
    proj.simulation_interval_max = _clamp_int(proj.simulation_interval_max, proj.simulation_interval_min, 3600)

    proj.pulse_event_inject_budget = _clamp_int(proj.pulse_event_inject_budget, 1, 100)

    proj.angelia_worker_per_agent = _clamp_int(proj.angelia_worker_per_agent, 1, 1)
    proj.angelia_event_max_attempts = _clamp_int(proj.angelia_event_max_attempts, 1, 20)
    proj.angelia_processing_timeout_sec = _clamp_int(proj.angelia_processing_timeout_sec, 5, 3600)
    proj.angelia_timer_idle_sec = _clamp_int(proj.angelia_timer_idle_sec, 5, 3600)
    proj.angelia_dedupe_window_sec = _clamp_int(proj.angelia_dedupe_window_sec, 0, 300)
    normalized_types = [str(x).strip() for x in proj.angelia_cooldown_preempt_types if str(x).strip() in _ALLOWED_TOOL_HINTS]
    proj.angelia_cooldown_preempt_types = normalized_types or ["mail_event", "manual"]

    proj.memory_compact_trigger_tokens = _clamp_int(proj.memory_compact_trigger_tokens, 2000, 256000)

    proj.context_token_budget_total = _clamp_int(proj.context_token_budget_total, 4000, 256000)
    proj.context_budget_task_state = _clamp_int(proj.context_budget_task_state, 200, 128000)
    proj.context_budget_observations = _clamp_int(proj.context_budget_observations, 200, 128000)
    proj.context_budget_inbox = _clamp_int(proj.context_budget_inbox, 200, 128000)
    proj.context_budget_inbox_unread = _clamp_int(proj.context_budget_inbox_unread, 100, 64000)
    proj.context_budget_inbox_read_recent = _clamp_int(proj.context_budget_inbox_read_recent, 100, 64000)
    proj.context_budget_inbox_receipts = _clamp_int(proj.context_budget_inbox_receipts, 100, 64000)
    proj.context_budget_state_window = _clamp_int(proj.context_budget_state_window, 200, 128000)
    proj.context_state_window_limit = _clamp_int(proj.context_state_window_limit, 1, 500)
    proj.context_observation_window = _clamp_int(proj.context_observation_window, 1, 500)
    proj.metis_refresh_mode = _fallback_str(
        proj.metis_refresh_mode,
        _ALLOWED_METIS_REFRESH_MODE,
        "pulse",
        "metis_refresh_mode",
        project_id,
    )

    proj.tool_loop_max = _clamp_int(proj.tool_loop_max, 1, 64)
    proj.tool_policies = _normalize_tool_policies(
        proj.tool_policies,
        project_id=project_id,
        owner="project",
        known_tools=known_tools,
    )

    # Strict agent id hygiene: avoid invalid folders/identities leaking into runtime.
    normalized_active: list[str] = []
    seen_active: set[str] = set()
    for aid in list(proj.active_agents or []):
        aa = str(aid or "").strip()
        if not is_valid_agent_id(aa):
            raise ValueError(
                f"invalid active_agents item '{aa}' in project '{project_id}': "
                "expected ^[a-z][a-z0-9_]{0,63}$ and not reserved human identity"
            )
        if aa in seen_active:
            continue
        seen_active.add(aa)
        normalized_active.append(aa)
    proj.active_agents = normalized_active

    proj.finalize_sleep_min_sec = _clamp_int(proj.finalize_sleep_min_sec, 5, 3600)
    proj.finalize_sleep_max_sec = _clamp_int(proj.finalize_sleep_max_sec, proj.finalize_sleep_min_sec, 86400)
    proj.finalize_sleep_default_sec = _clamp_int(
        proj.finalize_sleep_default_sec,
        proj.finalize_sleep_min_sec,
        proj.finalize_sleep_max_sec,
    )

    proj.debug_trace_max_events = _clamp_int(proj.debug_trace_max_events, 10, 2000)
    proj.llm_global_max_concurrency = _clamp_int(proj.llm_global_max_concurrency, 1, 256)
    proj.llm_global_rate_per_minute = _clamp_int(proj.llm_global_rate_per_minute, 1, 200000)
    proj.llm_project_max_concurrency = _clamp_int(proj.llm_project_max_concurrency, 1, 256)
    proj.llm_project_rate_per_minute = _clamp_int(proj.llm_project_rate_per_minute, 1, 200000)
    proj.llm_acquire_timeout_sec = _clamp_int(proj.llm_acquire_timeout_sec, 1, 300)
    proj.llm_retry_interval_ms = _clamp_int(proj.llm_retry_interval_ms, 10, 5000)

    proj.command_max_parallel = _clamp_int(proj.command_max_parallel, 1, 64)
    proj.command_timeout_sec = _clamp_int(proj.command_timeout_sec, 1, 3600)
    proj.command_max_memory_mb = _clamp_int(proj.command_max_memory_mb, 128, 32768)
    proj.command_max_cpu_sec = _clamp_int(proj.command_max_cpu_sec, 1, 600)
    proj.command_max_output_chars = _clamp_int(proj.command_max_output_chars, 512, 200000)

    proj.docker_cpu_limit = _clamp_float(proj.docker_cpu_limit, 0.1, 64.0)
    proj.docker_memory_limit_mb = _clamp_int(proj.docker_memory_limit_mb, 128, 65536)

    proj.detach_max_running_per_agent = _clamp_int(proj.detach_max_running_per_agent, 1, 64)
    proj.detach_max_running_per_project = _clamp_int(proj.detach_max_running_per_project, 1, 256)
    proj.detach_queue_max_per_agent = _clamp_int(proj.detach_queue_max_per_agent, 1, 256)
    proj.detach_ttl_sec = _clamp_int(proj.detach_ttl_sec, 30, 86400)
    proj.detach_stop_grace_sec = _clamp_int(proj.detach_stop_grace_sec, 1, 120)
    proj.detach_log_tail_chars = _clamp_int(proj.detach_log_tail_chars, 500, 200000)

    proj.hermes_default_timeout_sec = _clamp_int(proj.hermes_default_timeout_sec, 1, 600)
    proj.hermes_default_rate_per_minute = _clamp_int(proj.hermes_default_rate_per_minute, 1, 100000)
    proj.hermes_default_max_concurrency = _clamp_int(proj.hermes_default_max_concurrency, 1, 128)

    weights = {}
    for k, v in (proj.pulse_priority_weights or {}).items():
        kk = str(k).strip()
        if kk in _ALLOWED_TOOL_HINTS:
            try:
                weights[kk] = _clamp_int(int(v), 1, 1000)
            except Exception:
                continue
    proj.pulse_priority_weights = {
        "mail_event": weights.get("mail_event", 100),
        "manual": weights.get("manual", 80),
        "system": weights.get("system", 60),
        "timer": weights.get("timer", 10),
    }

    for aid, settings in list((proj.agent_settings or {}).items()):
        if not is_valid_agent_id(aid):
            raise ValueError(
                f"invalid agent_settings key '{aid}' in project '{project_id}': "
                "expected ^[a-z][a-z0-9_]{0,63}$ and not reserved human identity"
            )
        if settings.context_strategy:
            settings.context_strategy = _fallback_str(
                settings.context_strategy,
                _ALLOWED_CONTEXT_STRATEGIES,
                "structured_v1",
                f"agent.{aid}.context_strategy",
                project_id,
            )
        if settings.phase_strategy:
            settings.phase_strategy = _require_allowed_str(
                settings.phase_strategy,
                _ALLOWED_PHASE_STRATEGIES,
                f"agent.{aid}.phase_strategy",
                project_id,
            )
        if settings.context_token_budget_total is not None:
            settings.context_token_budget_total = _clamp_int(settings.context_token_budget_total, 4000, 256000)
        if settings.metis_refresh_mode:
            settings.metis_refresh_mode = _fallback_str(
                settings.metis_refresh_mode,
                _ALLOWED_METIS_REFRESH_MODE,
                "pulse",
                f"agent.{aid}.metis_refresh_mode",
                project_id,
            )
        settings.tool_policies = _normalize_tool_policies(
            settings.tool_policies,
            project_id=project_id,
            owner=f"agent.{aid}",
            known_tools=known_tools,
        )

    return proj


def normalize_system_config(cfg: SystemConfig) -> SystemConfig:
    if not cfg.projects:
        cfg.projects = {"default": ProjectConfig(name="Default World")}

    normalized: dict[str, ProjectConfig] = {}
    for pid, proj in cfg.projects.items():
        name = str(pid).strip()
        if not name:
            continue
        normalized[name] = normalize_project_config(name, proj)
    if "default" not in normalized:
        normalized["default"] = ProjectConfig(name="Default World")

    cfg.projects = normalized
    if cfg.current_project not in cfg.projects:
        cfg.current_project = "default"
    return cfg
