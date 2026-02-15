from __future__ import annotations

from argparse import Namespace

from cli.commands.config import cmd_config


class _Resp:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _base_payload() -> dict:
    return {
        "current_project": "p1",
        "has_openrouter_api_key": False,
        "projects": {
            "p1": {
                "agent_settings": {
                    "ground": {
                        "disabled_tools": ["send_message"],
                    }
                }
            }
        },
    }


def test_config_set_agent_disabled_tools(monkeypatch):
    posted = {}

    def fake_get(url, *args, **kwargs):
        return _Resp(_base_payload())

    def fake_post(url, json=None, *args, **kwargs):
        posted["json"] = json
        return _Resp({"status": "success"}, status_code=200)

    monkeypatch.setattr("cli.commands.config.requests.get", fake_get)
    monkeypatch.setattr("cli.commands.config.requests.post", fake_post)

    args = Namespace(
        subcommand="set",
        key="agent.ground.disabled_tools",
        value="check_inbox, send_message,check_inbox",
        project=None,
    )
    cmd_config(args)

    settings = posted["json"]["projects"]["p1"]["agent_settings"]["ground"]
    assert settings["disabled_tools"] == ["check_inbox", "send_message"]


def test_config_set_agent_disable_enable_tool(monkeypatch):
    posted = {"calls": []}

    def fake_get(url, *args, **kwargs):
        return _Resp(_base_payload())

    def fake_post(url, json=None, *args, **kwargs):
        posted["calls"].append(json)
        return _Resp({"status": "success"}, status_code=200)

    monkeypatch.setattr("cli.commands.config.requests.get", fake_get)
    monkeypatch.setattr("cli.commands.config.requests.post", fake_post)

    args_disable = Namespace(
        subcommand="set",
        key="agent.ground.disable_tool",
        value="check_inbox",
        project=None,
    )
    cmd_config(args_disable)

    first_settings = posted["calls"][-1]["projects"]["p1"]["agent_settings"]["ground"]
    assert "check_inbox" in first_settings["disabled_tools"]
    assert "send_message" in first_settings["disabled_tools"]

    def fake_get_after_disable(url, *args, **kwargs):
        payload = _base_payload()
        payload["projects"]["p1"]["agent_settings"]["ground"]["disabled_tools"] = first_settings["disabled_tools"]
        return _Resp(payload)

    monkeypatch.setattr("cli.commands.config.requests.get", fake_get_after_disable)

    args_enable = Namespace(
        subcommand="set",
        key="agent.ground.enable_tool",
        value="send_message",
        project=None,
    )
    cmd_config(args_enable)

    second_settings = posted["calls"][-1]["projects"]["p1"]["agent_settings"]["ground"]
    assert "send_message" not in second_settings["disabled_tools"]
    assert "check_inbox" in second_settings["disabled_tools"]
