"""Interaction event contracts and constants."""
from __future__ import annotations

EVENT_MESSAGE_SENT = "interaction.message.sent"
EVENT_MESSAGE_READ = "interaction.message.read"
EVENT_HERMES_NOTICE = "interaction.hermes.notice"
EVENT_DETACH_NOTICE = "interaction.detach.notice"
EVENT_AGENT_TRIGGER = "interaction.agent.trigger"

INTERACTION_EVENT_TYPES = {
    EVENT_MESSAGE_SENT,
    EVENT_MESSAGE_READ,
    EVENT_HERMES_NOTICE,
    EVENT_DETACH_NOTICE,
    EVENT_AGENT_TRIGGER,
}

