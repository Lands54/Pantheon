from gods.agents.base import GodAgent


def test_tool_status_does_not_misclassify_error_field_in_json_payload():
    result = '[{"id":"x","status":"handled","error":""}]'
    assert GodAgent._classify_tool_status(result) == "ok"


def test_tool_status_detects_explicit_path_error_with_cwd_prefix():
    result = "[Current CWD: /tmp] Content: Path Error: file not found."
    assert GodAgent._classify_tool_status(result) == "error"


def test_tool_status_detects_run_command_exit_code():
    ok = "Manifestation Result (exit=0):\nSTDOUT: hi\nSTDERR: "
    bad = "Manifestation Result (exit=1):\nSTDOUT: \nSTDERR: fail"
    assert GodAgent._classify_tool_status(ok) == "ok"
    assert GodAgent._classify_tool_status(bad) == "error"
