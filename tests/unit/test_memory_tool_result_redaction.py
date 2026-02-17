from gods.mnemosyne.intent_builders import intent_from_tool_result


def test_tool_result_compact_redacts_noisy_ids():
    payload = (
        "Revelation sent. event_id=abc123456789def0 "
        "outbox_receipt_id=ff00112233445566 "
        "mid=9988776655443322 "
        '{"message_id":"1122334455667788","id":"deadbeefcafebabe","ok":true}'
    )
    intent = intent_from_tool_result(
        project_id="p",
        agent_id="a",
        tool_name="send_message",
        status="ok",
        args={},
        result=payload,
    )
    compact = str(intent.payload.get("result_compact", ""))
    assert "event_id=<redacted>" in compact
    assert "outbox_receipt_id=<redacted>" in compact
    assert "mid=<redacted>" in compact
    assert '"message_id":"<redacted>"' in compact
    assert '"id":"<redacted>"' in compact
