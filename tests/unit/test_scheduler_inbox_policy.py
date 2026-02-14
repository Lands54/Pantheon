from api import scheduler


def test_pick_pulse_batch_skips_inbox_urgent_when_check_inbox_disabled(monkeypatch):
    monkeypatch.setattr(
        scheduler,
        "_get_status",
        lambda project_id, agent_id: {"status": "idle", "next_eligible_at": 10**12},
    )
    monkeypatch.setattr(scheduler, "has_pending_inbox", lambda project_id, agent_id: True)
    monkeypatch.setattr(scheduler, "is_tool_disabled", lambda project_id, agent_id, tool_name: True)

    batch = scheduler.pick_pulse_batch("p", ["a"], batch_size=4)
    assert batch == []


def test_pick_pulse_batch_uses_inbox_urgent_when_check_inbox_enabled(monkeypatch):
    monkeypatch.setattr(
        scheduler,
        "_get_status",
        lambda project_id, agent_id: {"status": "idle", "next_eligible_at": 10**12},
    )
    monkeypatch.setattr(scheduler, "has_pending_inbox", lambda project_id, agent_id: True)
    monkeypatch.setattr(scheduler, "is_tool_disabled", lambda project_id, agent_id, tool_name: False)

    batch = scheduler.pick_pulse_batch("p", ["a"], batch_size=4)
    assert batch == [("a", "inbox_event")]

