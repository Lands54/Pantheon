from pathlib import Path
import shutil

import pytest

from gods import events as events_bus


def test_event_bus_rejects_business_state_fields():
    project_id = "unit_event_bus_transport_only"
    try:
        rec = events_bus.EventRecord.create(
            project_id=project_id,
            domain="iris",
            event_type="mail_event",
            priority=100,
            payload={"agent_id": "a", "delivered_at": 1.23},
        )
        with pytest.raises(ValueError):
            events_bus.append_event(rec)
    finally:
        shutil.rmtree(Path("projects") / project_id, ignore_errors=True)
