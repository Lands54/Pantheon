"""Janus message assembler."""
from __future__ import annotations

from langchain_core.messages import SystemMessage

from gods.janus.models import ContextBuildResult


def assemble_llm_messages(result: ContextBuildResult) -> list:
    system_text = "\n\n".join([x for x in result.system_blocks if x])
    # Zero-compat card-only context: Janus emits only a single system block message.
    return [SystemMessage(content=system_text)]
