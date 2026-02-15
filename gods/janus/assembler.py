"""Janus message assembler."""
from __future__ import annotations

from langchain_core.messages import SystemMessage

from gods.janus.models import ContextBuildResult


def assemble_llm_messages(result: ContextBuildResult) -> list:
    system_text = "\n\n".join([x for x in result.system_blocks if x])
    return [SystemMessage(content=system_text)] + list(result.recent_messages or [])
