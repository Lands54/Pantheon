"""Communication use-case service."""
from __future__ import annotations

import logging
from typing import Any

from gods.config import runtime_config
from gods.iris import enqueue_message
from gods.angelia.pulse import get_priority_weights, is_inbox_event_enabled

logger = logging.getLogger("GodsServer")


class CommunicationService:
    def confess(self, agent_id: str, title: str, message: str, silent: bool = False) -> dict[str, Any]:
        project_id = runtime_config.current_project
        weights = get_priority_weights(project_id)
        trigger_pulse = (not bool(silent)) and is_inbox_event_enabled(project_id)
        res = enqueue_message(
            project_id=project_id,
            agent_id=agent_id,
            sender="High Overseer",
            title=title,
            content=message,
            msg_type="confession",
            trigger_pulse=trigger_pulse,
            pulse_priority=int(weights.get("inbox_event", 100)),
        )
        if trigger_pulse:
            logger.info(f"⚡ Inbox event queued for {agent_id} in {project_id}")
            status = "Confession delivered and pulse enqueued"
        else:
            status = "Confession delivered silently (no immediate pulse)"
        return {"status": status, **res}


communication_service = CommunicationService()
