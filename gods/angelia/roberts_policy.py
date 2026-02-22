"""Policy constants for Robert Rules engine."""
from __future__ import annotations

from typing import Any

DEFAULT_RULES_PROFILE = "roberts_core_v1"

# action type -> votes needed mode
# simple_majority: yes > no
# two_thirds: yes >= ceil(2/3 * votes_cast)
ACTION_VOTE_RULES: dict[str, str] = {
    "vote_cast": "simple_majority",
    "procedural_call_question": "two_thirds",
    "procedural_table_motion": "simple_majority",
    "reconsider_submit": "simple_majority",
}

CHAIR_ACTIONS = {
    "pause": "chair_override_pause",
    "resume": "chair_override_resume",
    "terminate": "chair_override_terminate",
    "skip_turn": "chair_override_skip_turn",
}


def default_timeouts() -> dict[str, int]:
    return {
        "speaker": 90,
        "action": 90,
        "vote": 120,
    }


def normalize_timeouts(raw: dict[str, Any] | None) -> dict[str, int]:
    out = default_timeouts()
    for k, v in dict(raw or {}).items():
        key = str(k or "").strip().lower()
        if key not in out:
            continue
        try:
            iv = int(v)
        except Exception:
            continue
        out[key] = max(10, min(iv, 3600))
    return out


def required_vote_rule(action_type: str) -> str:
    return ACTION_VOTE_RULES.get(str(action_type or "").strip(), "simple_majority")
