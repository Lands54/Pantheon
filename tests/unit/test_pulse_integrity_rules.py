from __future__ import annotations

from gods.mnemosyne.facade import group_pulses, validate_pulse_integrity


def test_integrity_fails_on_missing_start_finish_and_result_pair():
    frames = group_pulses(
        [
            {
                "seq": 1,
                "project_id": "p",
                "agent_id": "a",
                "pulse_id": "p1",
                "kind": "trigger.event",
                "ts": 1.0,
                "payload": {"event_type": "manual"},
                "origin": "angelia",
                "trace_id": "",
            },
            {
                "seq": 2,
                "project_id": "p",
                "agent_id": "a",
                "pulse_id": "p1",
                "kind": "tool.result",
                "ts": 2.0,
                "payload": {"call_id": "c1"},
                "origin": "internal",
                "trace_id": "",
            },
        ]
    )
    report = validate_pulse_integrity(frames)
    blob = " | ".join(report.all_issues)
    assert "missing pulse.start" in blob
    assert "pulse.finish" in blob.lower()
    assert "tool.result without tool.call" in blob
