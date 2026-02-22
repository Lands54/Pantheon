"""Contracts for sequential_v1 tagged pulse context rendering."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


TriggerKind = Literal["event", "email"]
IntentOrigin = Literal["angelia", "external", "internal"]
IntentLane = Literal["trigger", "agentresponse", "tool", "other"]


@dataclass
class PulseTriggerItem:
    kind: TriggerKind
    origin: IntentOrigin = "external"
    item_type: str = ""
    item_id: str = ""
    title: str = ""
    sender: str = ""
    content: str = ""


@dataclass
class PulseToolCallItem:
    name: str
    call_id: str
    status: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    result: str = ""


@dataclass
class PulseAgentResponseSegment:
    kind: Literal["text", "tool"] = "text"
    seq: int = 0
    text: str = ""
    tool_call: PulseToolCallItem | None = None


@dataclass
class PulseAgentResponse:
    text: str = ""
    tool_calls: list[PulseToolCallItem] = field(default_factory=list)
    segments: list[PulseAgentResponseSegment] = field(default_factory=list)


@dataclass
class PulseFrame:
    pulse_id: str
    timestamp: float = 0.0
    state: Literal["processing", "done"] = "processing"
    triggers: list[PulseTriggerItem] = field(default_factory=list)
    agent_response: PulseAgentResponse = field(default_factory=PulseAgentResponse)


@dataclass
class XmlIntentAtom:
    pulse_id: str
    intent_key: str
    source_kind: str
    origin: IntentOrigin
    lane: IntentLane
    timestamp: float
    anchor_seq: int = 0
    item_type: str = ""
    item_id: str = ""
    title: str = ""
    sender: str = ""
    content: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    result: str = ""
    call_id: str = ""
    status: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)
