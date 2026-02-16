"""Structured Janus context strategy with budgeted sections."""
from __future__ import annotations

from typing import Any

from gods.inbox.service import build_inbox_overview
from gods.janus.journal import list_observations, read_profile, read_task_state
from gods.janus.models import ContextBuildRequest, ContextBuildResult
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
        b_recent = int(cfg.get("budget_recent_messages", 12000))
        recent_limit = int(cfg.get("recent_message_limit", 50))
        obs_window = int(cfg.get("observation_window", 30))
        include_inbox_hints = bool(cfg.get("include_inbox_status_hints", True))

        profile = read_profile(req.project_id, req.agent_id)
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

        # Keep recent messages by dynamic token budget instead of fixed [-8].
        src_recent = (req.state.get("messages", []) or [])[-max(1, recent_limit) :]
        kept_recent = []
        used_recent_tokens = 0
        for m in reversed(src_recent):
            content = str(getattr(m, "content", "") or "")
            t = _tok_len(content)
            if used_recent_tokens + t > b_recent:
                continue
            kept_recent.append(m)
            used_recent_tokens += t
        kept_recent.reverse()

        policy_block = (
            "Policy:\n"
            "- Follow phase/tool policy constraints strictly.\n"
            "- Prefer progressing objective with productive actions.\n"
            "- Avoid repeated same tool+args when no new evidence appears."
        )

        system_blocks = [
            f"# IDENTITY\n{_clip_by_tokens(profile, 3000)}\nProject: {req.project_id}",
            f"# TASK STATE\n{task_block}",
            f"# INBOX\n{inbox_block}",
            f"# OBSERVATIONS\n{obs_block}",
            f"# LOCAL MEMORY (recent excerpt)\n{_clip_by_tokens(req.local_memory or '', 4000)}",
            f"# PHASE\nCurrent Phase: {req.phase_name}\n{req.phase_block}",
            f"# TOOLS\n{req.tools_desc}",
            f"# EXECUTION POLICY\n{policy_block}",
        ]

        usage = {
            "task_tokens": _tok_len(task_block),
            "obs_tokens": _tok_len(obs_block),
            "inbox_tokens": _tok_len(inbox_block),
            "recent_tokens": used_recent_tokens,
            "recent_messages": len(kept_recent),
        }
        preview = {
            "mode": self.name,
            "recent_messages": len(kept_recent),
            "selected_observations": len(selected),
            "phase": req.phase_name,
        }
        return ContextBuildResult(
            strategy_used=self.name,
            system_blocks=system_blocks,
            recent_messages=kept_recent,
            token_usage=usage,
            preview=preview,
        )
