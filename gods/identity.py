"""Shared identity constants."""
from __future__ import annotations

import re

HUMAN_AGENT_ID = "human.overseer"
AGENT_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def is_valid_agent_id(value: str) -> bool:
    aid = str(value or "").strip()
    if not aid:
        return False
    if aid == HUMAN_AGENT_ID:
        return False
    return bool(AGENT_ID_RE.match(aid))
