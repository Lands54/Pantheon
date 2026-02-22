from gods.mnemosyne import facade as mnemosyne_facade


def test_llm_response_allows_pulse_id_and_anchor_seq():
    mnemosyne_facade.validate_intent_contract(
        "llm.response",
        "llm",
        {"phase": "react_graph", "content": "ok", "anchor_seq": 10, "pulse_id": "pulse_x"},
    )


def test_tool_contracts_allow_pulse_id():
    mnemosyne_facade.validate_intent_contract(
        "tool.call.list",
        "tool",
        {"tool_name": "list", "args": {}, "call_id": "c1", "node": "dispatch_tools", "pulse_id": "p1"},
    )
    mnemosyne_facade.validate_intent_contract(
        "tool.list.ok",
        "tool",
        {"tool_name": "list", "status": "ok", "args": {}, "result": "r", "result_compact": "r", "call_id": "c1", "pulse_id": "p1"},
    )
