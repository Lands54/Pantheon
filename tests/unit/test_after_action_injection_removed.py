from gods.agents.runtime import nodes


class _DummyAgent:
    project_id = "p"
    agent_id = "alpha"

    def execute_tool(self, name, args, node_name="", pulse_id=""):
        return "ok"

    def _record_intent(self, intent):
        raise AssertionError("dispatch_tools_node should not record event_injected intent anymore")

    def _finalize_control_from_args(self, args):
        return {}


def test_dispatch_tools_no_after_action_injection_path(monkeypatch):
    monkeypatch.setattr(nodes, "_strategy_envelope", lambda *args, **kwargs: object())
    state = {
        "tool_calls": [{"name": "list", "args": {"path": "."}, "id": "c1"}],
        "messages": [],
        "strategy": "react_graph",
        "project_id": "p",
        "agent_id": "alpha",
    }
    out = nodes.dispatch_tools_node(_DummyAgent(), state)
    assert isinstance(out.get("tool_results", []), list)
