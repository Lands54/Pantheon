from __future__ import annotations

from gods.mnemosyne.facade import append_pulse_entries, list_pulse_entries


def test_pulse_ledger_append_and_range_query():
    project_id = "unit_pulse_ledger_append"
    agent_id = "alpha"
    rows = append_pulse_entries(
        project_id,
        agent_id,
        [
            {"pulse_id": "p1", "kind": "pulse.start", "payload": {"reason": "manual"}, "origin": "angelia"},
            {"pulse_id": "p1", "kind": "trigger.event", "payload": {"event_type": "manual"}, "origin": "angelia"},
            {"pulse_id": "p1", "kind": "pulse.finish", "payload": {}, "origin": "angelia"},
        ],
    )
    assert len(rows) == 3
    assert int(rows[0]["seq"]) + 1 == int(rows[1]["seq"])
    assert int(rows[1]["seq"]) + 1 == int(rows[2]["seq"])

    out_all = list_pulse_entries(project_id, agent_id, from_seq=0, limit=100)
    assert len(out_all) >= 3
    tail = out_all[-3:]
    assert [str(x["kind"]) for x in tail] == ["pulse.start", "trigger.event", "pulse.finish"]

    out_delta = list_pulse_entries(project_id, agent_id, from_seq=int(tail[0]["seq"]), limit=100)
    assert [str(x["kind"]) for x in out_delta][-2:] == ["trigger.event", "pulse.finish"]
