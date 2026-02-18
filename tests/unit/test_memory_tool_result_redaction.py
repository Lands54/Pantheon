from gods.mnemosyne.facade import intent_from_tool_result
from gods.mnemosyne import record_intent


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


def test_read_file_only_chronicle_is_redacted_not_raw_intent_payload():
    result_text = (
        "[Current CWD: /tmp] Content: [READ]\n"
        "path: src/secret.txt\n"
        "resolved_path: /tmp/src/secret.txt\n"
        "line_range: 1-2\n"
        "total_lines: 99\n"
        "---\n"
        "TOP-SECRET-LINE-1\nTOP-SECRET-LINE-2\n"
    )
    intent = intent_from_tool_result(
        project_id="p",
        agent_id="a",
        tool_name="read",
        status="ok",
        args={"path": "src/secret.txt", "start": 1, "end": 2},
        result=result_text,
    )
    # raw payload is preserved (for non-chronicle sinks such as context/runtime)
    raw = str(intent.payload.get("result", ""))
    assert "TOP-SECRET-LINE-1" in raw

    # chronicle render is redacted
    out = record_intent(intent)
    chronicle_text = str(out.get("chronicle_text", ""))
    assert "content=omitted" in chronicle_text
    assert "resolved_path=/tmp/src/secret.txt" in chronicle_text
    assert "TOP-SECRET-LINE-1" not in chronicle_text
