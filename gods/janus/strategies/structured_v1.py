"""Structured Janus context strategy with budgeted sections."""
from __future__ import annotations

from typing import Any

from gods.janus.models import ContextBuildRequest, ContextBuildResult, TaskStateCard
from gods.janus.strategy_base import ContextStrategy


def _tok_len(text: str) -> int:
    # Approximation: 1 token ~= 4 chars for mixed CJK/EN prompt accounting.
    return max(1, len(text) // 4)


def _clip_by_tokens(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _render_task_state(card) -> str:
    lines = [f"Objective: {card.objective}"]
    if card.plan:
        lines.append("Plan:")
        lines.extend([f"- {x}" for x in card.plan[:10]])
    if card.progress:
        lines.append("Progress:")
        lines.extend([f"- {x}" for x in card.progress[:12]])
    if card.blockers:
        lines.append("Blockers:")
        lines.extend([f"- {x}" for x in card.blockers[:8]])
    if card.next_actions:
        lines.append("Next Actions:")
        lines.extend([f"- {x}" for x in card.next_actions[:8]])
    return "\n".join(lines)


def _pick_observations(rows: list[dict[str, Any]], window: int) -> list[dict[str, Any]]:
    rows = list(rows or [])[-max(1, window) :]
    fails = [r for r in rows if str(r.get("status", "")).lower() in {"error", "blocked", "failed"}]
    important_keywords = ("commit", "disable", "start", "stop", "register")
    impactful = [
        r
        for r in rows
        if any(k in str(r.get("tool", "")).lower() for k in important_keywords)
        and r not in fails
    ]
    normal = [r for r in rows if r not in fails and r not in impactful]
    picked = fails[-10:] + impactful[-10:] + normal[-10:]
    # keep order by timestamp after selection
    picked.sort(key=lambda x: float(x.get("timestamp", 0.0)))
    return picked


def _render_observations(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(no structured observations yet)"
    lines = []
    for r in rows:
        tool = str(r.get("tool", ""))
        st = str(r.get("status", ""))
        ts = float(r.get("timestamp", 0.0))
        args_s = str(r.get("args_summary", ""))
        res_s = str(r.get("result_summary", ""))
        lines.append(f"- t={ts:.3f} tool={tool} status={st} args={args_s} result={res_s}")
    return "\n".join(lines)


def _message_role(msg: Any) -> str:
    t = str(getattr(msg, "type", "") or "").lower()
    if t:
        return t
    cls = msg.__class__.__name__.lower()
    if "human" in cls:
        return "human"
    if "tool" in cls:
        return "tool"
    if "ai" in cls:
        return "ai"
    if "system" in cls:
        return "system"
    return "message"


def _render_state_window(messages: list[Any], recent_limit: int, token_budget: int) -> tuple[str, int, int]:
    src_recent = list(messages or [])[-max(1, recent_limit) :]
    kept_recent: list[Any] = []
    used_recent_tokens = 0
    for m in reversed(src_recent):
        content = str(getattr(m, "content", "") or "")
        t = _tok_len(content)
        if used_recent_tokens + t > token_budget:
            continue
        kept_recent.append(m)
        used_recent_tokens += t
    kept_recent.reverse()
    if not kept_recent:
        return "(no in-pulse state messages)", 0, 0

    lines = []
    for m in kept_recent:
        role = _message_role(m)
        name = str(getattr(m, "name", "") or "")
        header = role if not name else f"{role}:{name}"
        content = str(getattr(m, "content", "") or "")
        lines.append(f"[{header}] {content}")
    return "\n".join(lines), len(kept_recent), used_recent_tokens


class StructuredV1ContextStrategy(ContextStrategy):
    name = "structured_v1"

    def build(self, req: ContextBuildRequest) -> ContextBuildResult:
        cfg = req.context_cfg
        b_task = int(cfg.get("budget_task_state", 4000))
        b_obs = int(cfg.get("budget_observations", 12000))
        b_inbox = int(cfg.get("budget_inbox", 4000))
        b_inbox_unread = int(cfg.get("budget_inbox_unread", 2000))
        b_inbox_read_recent = int(cfg.get("budget_inbox_read_recent", 1000))
        b_inbox_receipts = int(cfg.get("budget_inbox_receipts", 1000))
        b_state_window = int(cfg.get("budget_state_window", 12000))
        state_window_limit = int(cfg.get("state_window_limit", 50))
        obs_window = int(cfg.get("observation_window", 30))
        include_inbox_hints = bool(cfg.get("include_inbox_status_hints", True))

        materials = dict(req.context_materials or req.state.get("__context_materials", {}) or {})
        if "triggers_rendered" not in materials:
            materials["triggers_rendered"] = [
                str(getattr(x, "fallback_text", "") or "").strip()
                for x in list(req.state.get("triggers", []) or [])
                if str(getattr(x, "fallback_text", "") or "").strip()
            ]
        if "mailbox_rendered" not in materials:
            materials["mailbox_rendered"] = [
                str(getattr(x, "fallback_text", "") or "").strip()
                for x in list(req.state.get("mailbox", []) or [])
                if str(getattr(x, "fallback_text", "") or "").strip()
            ]
        if "state_window_messages" not in materials:
            materials["state_window_messages"] = list(req.state.get("messages", []) or [])
        profile = str(materials.get("profile", "") or "")
        chronicle = str(materials.get("chronicle", "") or req.local_memory or "")
        ts = dict(materials.get("task_state", {}) or {})
        task_state = TaskStateCard(
            objective=str(ts.get("objective", str(req.state.get("context", "")))),
            plan=list(ts.get("plan", []) or []),
            progress=list(ts.get("progress", []) or []),
            blockers=list(ts.get("blockers", []) or []),
            next_actions=list(ts.get("next_actions", []) or []),
        )

        obs_rows = list(materials.get("observations", []) or [])
        selected = _pick_observations(obs_rows, obs_window)

        trigger_lines = [f"- {str(x)}" for x in list(materials.get("triggers_rendered", []) or []) if str(x).strip()]
        trigger_text = "\n".join(trigger_lines) if trigger_lines else "(no specific trigger events)"

        mailbox_lines = [str(x) for x in list(materials.get("mailbox_rendered", []) or []) if str(x).strip()]
        mailbox_block = "\n".join(mailbox_lines) if mailbox_lines else "(no mailbox updates in this pulse)"

        task_block = _clip_by_tokens(_render_task_state(task_state), b_task)
        obs_block = _clip_by_tokens(_render_observations(selected), b_obs)
        inbox_hint_block = str(req.inbox_hint or "").strip()



        state_window_block, state_window_count, state_window_tokens = _render_state_window(
            list(materials.get("state_window_messages", []) or []),
            recent_limit=state_window_limit,
            token_budget=b_state_window,
        )
        combined_memory_block = (
            "[CHRONICLE]\n"
            f"{chronicle or '(no chronicle yet)'}\n\n"
            "[STATE_WINDOW]\n"
            f"{state_window_block}"
        )

        system_blocks = [
            f"# COMBINED MEMORY\n{combined_memory_block}",
            f"# IDENTITY\n{_clip_by_tokens(profile, 3000)}\nProject: {req.project_id}",
            f"# TASK STATE\n{task_block}",
            f"# OBSERVATIONS\n{obs_block}",
            f"# TRIGGER\n{trigger_text}",
            f"# MAILBOX\n{mailbox_block}",
            f"# DIRECTIVES\n{req.directives}",
            f"# PHASE\nCurrent Phase: {req.phase_name}\n{req.phase_block}",
            f"# TOOLS\n{req.tools_desc}",
        ]
        if include_inbox_hints and inbox_hint_block:
            system_blocks.insert(5, f"# INBOX_HINT\n{inbox_hint_block}")

        usage = {
            "chronicle_tokens": _tok_len(chronicle),
            "combined_memory_tokens": _tok_len(combined_memory_block),
            "state_window_tokens": state_window_tokens,
            "state_window_messages": state_window_count,
            "task_tokens": _tok_len(task_block),
            "obs_tokens": _tok_len(obs_block),
            "mailbox_tokens": _tok_len(mailbox_block),
        }
        preview = {
            "mode": self.name,
            "state_window_messages": state_window_count,
            "selected_observations": len(selected),
            "phase": req.phase_name,
        }
        return ContextBuildResult(
            strategy_used=self.name,
            system_blocks=system_blocks,
            recent_messages=[],
            token_usage=usage,
            preview=preview,
        )
