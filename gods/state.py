"""
LangGraph 状态定义 - Gods Platform
"""
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
from gods.mnemosyne import MemoryIntent


class GodsState(TypedDict, total=False):
    """
    Global state definition for the Gods platform, used in the LangGraph runtime.
    """
    project_id: str
    messages: Annotated[list, add_messages]
    context: str
    next_step: str
    abstained: list
    triggers: list[MemoryIntent]
    # mailbox 是统一消息域上下文，包含 inbox 事件与 outbox 回执。
    mailbox: list[MemoryIntent]
