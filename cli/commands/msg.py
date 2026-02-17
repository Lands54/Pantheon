"""CLI human-friendly message commands."""
from __future__ import annotations

import json

import requests

from cli.utils import get_base_url
from gods.identity import HUMAN_AGENT_ID


def _pid(args) -> str:
    base = get_base_url()
    try:
        cfg = requests.get(f"{base}/config", timeout=3).json()
        return args.project or cfg.get("current_project", "default")
    except Exception:
        return args.project or "default"


def cmd_msg(args):
    base = get_base_url()
    pid = _pid(args)

    if args.subcommand == "send":
        payload = {
            "to_id": args.to,
            "sender_id": args.sender or HUMAN_AGENT_ID,
            "title": args.title,
            "content": args.content,
            "msg_type": args.msg_type,
            "trigger_pulse": not bool(args.no_pulse),
        }
        req = {
            "project_id": pid,
            "domain": "interaction",
            "event_type": "interaction.message.sent",
            "payload": payload,
            "max_attempts": int(args.max_attempts),
        }
        res = requests.post(f"{base}/events/submit", json=req, timeout=10)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        return

