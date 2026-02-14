"""
LangGraph 状态定义 - Gods Platform
"""
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages


class GodsState(TypedDict):
    """众神系统的全局状态"""
    project_id: str  # 当前项目名称
    messages: Annotated[list, add_messages]  # 消息历史
    summary: str  # 历史记忆的压缩摘要 (长期记忆)
    current_speaker: str  # 当前发言的 God
    debate_round: int  # 辩论轮次
    inbox: dict  # agent_id -> [messages]
    context: str  # 当前上下文
    next_step: str  # 用于控制 ReAct 循环 (continue | finish | escalated | abstained)
    abstained: list  # list of agent_ids who opted out of this thread
