"""Structured Janus context strategy with budgeted sections."""
from __future__ import annotations

from typing import Any

from gods.inbox.service import build_inbox_overview
from gods.janus.journal import list_observations, read_profile, read_task_state
from gods.janus.models import ContextBuildRequest, ContextBuildResult
from gods.janus.strategy_base import ContextStrategy
from gods.mnemosyne.compaction import load_chronicle_for_context


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

        profile = read_profile(req.project_id, req.agent_id)
        chronicle = load_chronicle_for_context(req.project_id, req.agent_id, fallback=req.local_memory or "")
        task_state = read_task_state(req.project_id, req.agent_id, objective_fallback=str(req.state.get("context", "")))

        obs_rows = list_observations(req.project_id, req.agent_id, limit=max(obs_window * 3, 30))
        selected = _pick_observations(obs_rows, obs_window)

        overview = build_inbox_overview(req.project_id, req.agent_id, budget=max(5, obs_window))
        inbox_text = (
            f"{overview}\n\n"
            "[INBOX ACCESS HINT]\n"
            + (req.inbox_hint or "")
        )
        if include_inbox_hints:
            inbox_text = (
                f"{inbox_text}\n"
                "Inbox State Note:\n"
                "- Messages delivered in this pulse are already injected into context.\n"
                "- Delivered message IDs will be marked handled after pulse completion by scheduler.\n"
                "- Do not repeatedly poll inbox for confirmation."
            )

        task_block = _clip_by_tokens(_render_task_state(task_state), b_task)
        obs_block = _clip_by_tokens(_render_observations(selected), b_obs)
        # Keep four logical sections under separate soft budgets before final clip.
        parts = inbox_text.split("\n\n")
        summary_part = parts[0] if len(parts) > 0 else ""
        unread_part = parts[1] if len(parts) > 1 else ""
        read_part = parts[2] if len(parts) > 2 else ""
        receipts_part = parts[3] if len(parts) > 3 else ""
        tail_parts = "\n\n".join(parts[4:]) if len(parts) > 4 else ""
        inbox_block = (
            _clip_by_tokens(summary_part, max(200, b_inbox_unread // 2))
            + "\n\n"
            + _clip_by_tokens(unread_part, b_inbox_unread)
            + "\n\n"
            + _clip_by_tokens(read_part, b_inbox_read_recent)
            + "\n\n"
            + _clip_by_tokens(receipts_part, b_inbox_receipts)
            + ("\n\n" + _clip_by_tokens(tail_parts, max(200, b_inbox // 4)) if tail_parts else "")
        )
        inbox_block = _clip_by_tokens(inbox_block, b_inbox)

        state_window_block, state_window_count, state_window_tokens = _render_state_window(
            req.state.get("messages", []) or [],
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
            f"# INBOX\n{inbox_block}",
            f"# DIRECTIVES\n{req.directives}",
            f"# PHASE\nCurrent Phase: {req.phase_name}\n{req.phase_block}",
            f"# TOOLS\n{req.tools_desc}",
        ]

        usage = {
            "chronicle_tokens": _tok_len(chronicle),
            "combined_memory_tokens": _tok_len(combined_memory_block),
            "state_window_tokens": state_window_tokens,
            "state_window_messages": state_window_count,
            "task_tokens": _tok_len(task_block),
            "obs_tokens_unused": _tok_len(obs_block),
            "inbox_tokens": _tok_len(inbox_block),
        }
        preview = {
            "mode": self.name,
            "state_window_messages": state_window_count,
            "selected_observations_unused": len(selected),
            "phase": req.phase_name,
        }
        return ContextBuildResult(
            strategy_used=self.name,
            system_blocks=system_blocks,
            recent_messages=[],
            token_usage=usage,
            preview=preview,
        )
