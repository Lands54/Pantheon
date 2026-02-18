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
                        "disabled_tools": [],
                    }
                }
            }
        },
    }


def test_config_set_agent_node_tools_allow(monkeypatch):
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
        key="agent.ground.node_tools.llm_think.allow",
        value="list,read,list",
        project=None,
    )
    cmd_config(args)
    assert posted == {}


def test_config_set_project_node_tools_allow(monkeypatch):
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
        key="tools.node.dispatch_tools.allow",
        value="finalize,post_to_synod,finalize",
        project=None,
    )
    cmd_config(args)
    assert posted == {}
