"""Context strategy runtime policy resolvers (Janus-owned)."""
from __future__ import annotations

from gods.config import runtime_config
from gods.janus.registry import DEFAULT_CONTEXT_STRATEGY, list_strategies


def _supported_context_strategies() -> set[str]:
    return {str(x).strip() for x in list_strategies() if str(x).strip()}


def _agent_settings(project_id: str, agent_id: str) -> dict:
    proj = runtime_config.projects.get(project_id)
    if not proj:
        return {}
    settings = proj.agent_settings.get(agent_id)
    if not settings:
        return {}
    data = settings.model_dump() if hasattr(settings, "model_dump") else {}
    return data if isinstance(data, dict) else {}


def resolve_context_strategy(project_id: str, agent_id: str) -> str:
    def _normalize(v: str | None) -> str:
        s = str(v or "").strip()
        if s in _supported_context_strategies():
            return s
        return DEFAULT_CONTEXT_STRATEGY

    s = _agent_settings(project_id, agent_id)
    val = s.get("context_strategy")
    if isinstance(val, str) and val.strip():
        return _normalize(val)
    proj = runtime_config.projects.get(project_id)
    if not proj:
        return DEFAULT_CONTEXT_STRATEGY
    return _normalize(str(getattr(proj, "context_strategy", DEFAULT_CONTEXT_STRATEGY) or DEFAULT_CONTEXT_STRATEGY))


def resolve_context_token_budget_total(project_id: str, agent_id: str) -> int:
    s = _agent_settings(project_id, agent_id)
    val = s.get("context_token_budget_total")
    if val is not None:
        try:
            return max(4000, int(val))
        except Exception:
            pass
    proj = runtime_config.projects.get(project_id)
    base = int(getattr(proj, "context_token_budget_total", 32000) if proj else 32000)
    return max(4000, base)


def resolve_context_cfg(project_id: str, agent_id: str) -> dict:
    proj = runtime_config.projects.get(project_id)
    cfg = {
        "strategy": resolve_context_strategy(project_id, agent_id),
        "token_budget_total": resolve_context_token_budget_total(project_id, agent_id),
        "budget_task_state": int(getattr(proj, "context_budget_task_state", 4000) if proj else 4000),

        "budget_inbox": int(getattr(proj, "context_budget_inbox", 4000) if proj else 4000),
        "budget_inbox_unread": int(getattr(proj, "context_budget_inbox_unread", 2000) if proj else 2000),
        "budget_inbox_read_recent": int(getattr(proj, "context_budget_inbox_read_recent", 1000) if proj else 1000),
        "budget_inbox_receipts": int(getattr(proj, "context_budget_inbox_receipts", 1000) if proj else 1000),
        "short_window_intents": int(getattr(proj, "context_short_window_intents", 120) if proj else 120),

        "include_inbox_status_hints": bool(getattr(proj, "context_include_inbox_status_hints", True) if proj else True),
        "write_build_report": bool(getattr(proj, "context_write_build_report", True) if proj else True),
        "n_recent": int(getattr(proj, "context_n_recent", 12) if proj else 12),
        "recent_token_budget": int(getattr(proj, "context_recent_token_budget", 6000) if proj else 6000),
        "token_budget_chronicle_trigger": int(getattr(proj, "context_token_budget_chronicle_trigger", 8000) if proj else 8000),
    }
    s = _agent_settings(project_id, agent_id)
    if s.get("context_token_budget_total") is not None:
        try:
            cfg["token_budget_total"] = max(4000, int(s["context_token_budget_total"]))
        except Exception:
            pass
    if s.get("context_strategy"):
        cfg["strategy"] = resolve_context_strategy(project_id, agent_id)
    return cfg
