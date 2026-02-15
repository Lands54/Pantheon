from types import SimpleNamespace

from gods.tools.execution import run_command


class _DummyBackend:
    def __init__(self):
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(exit_code=0, stdout="ok", stderr="", error_code="", error_message="", timed_out=False)


def test_run_command_dispatches_to_backend(monkeypatch):
    dummy = _DummyBackend()

    monkeypatch.setattr("gods.tools.execution.resolve_execution_backend", lambda project_id: dummy)

    out = run_command.invoke(
        {
            "command": "echo hello",
            "caller_id": "tester",
            "project_id": "default",
        }
    )
    assert "exit=0" in out
    assert dummy.calls
    payload = dummy.calls[0]
    assert payload["project_id"] == "default"
    assert payload["agent_id"] == "tester"
    assert payload["command_text"] == "echo hello"
