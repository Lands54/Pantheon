"""
LangGraph 状态定义 - Gods Platform
"""
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages


class GodsState(TypedDict):
    """众神系统的全局状态"""
    messages: Annotated[list, add_messages]  # 消息历史，使用 add_messages 实现增量合并
    current_speaker: str  # 当前发言的 God
    debate_round: int  # 辩论轮次
    inbox: dict  # agent_id -> [messages]
    context: str  # 当前上下文
    next_step: str  # 用于控制 ReAct 循环 (continue | finish)
