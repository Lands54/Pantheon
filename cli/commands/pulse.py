"""CLI pulse event queue command handlers."""
from __future__ import annotations

import json

import requests

from cli.utils import get_base_url


def cmd_pulse(args):
    base = get_base_url()
    try:
        cfg = requests.get(f"{base}/config", timeout=3).json()
        pid = args.project or cfg.get("current_project", "default")
    except Exception:
        pid = args.project or "default"

    if args.subcommand == "queue":
        try:
            params = {
                "agent_id": args.agent or "",
                "status": args.status,
                "limit": args.limit,
            }
            res = requests.get(f"{base}/projects/{pid}/pulse/queue", params=params, timeout=10)
            data = res.json()
            print(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ pulse queue failed: {e}")

    elif args.subcommand == "push":
        try:
            payload = {
                "agent_id": args.agent,
                "event_type": args.type,
                "payload": {},
            }
            res = requests.post(f"{base}/projects/{pid}/pulse/enqueue", json=payload, timeout=10)
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ pulse push failed: {e}")
