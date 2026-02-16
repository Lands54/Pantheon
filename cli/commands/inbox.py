"""CLI inbox event command handlers."""
from __future__ import annotations

import json

import requests

from cli.utils import get_base_url


def cmd_inbox(args):
    print("⚠️  Deprecated: use `temple.sh angelia events --type inbox_event` for wake-queue facts.")
    base = get_base_url()
    try:
        cfg = requests.get(f"{base}/config", timeout=3).json()
        pid = args.project or cfg.get("current_project", "default")
    except Exception:
        pid = args.project or "default"

    if args.subcommand == "events":
        try:
            params = {
                "agent_id": args.agent or "",
                "state": args.state or "",
                "limit": args.limit,
            }
            res = requests.get(f"{base}/projects/{pid}/inbox/events", params=params, timeout=10)
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ inbox events failed: {e}")
    elif args.subcommand == "outbox":
        try:
            params = {
                "from_agent_id": args.agent or "",
                "to_agent_id": args.to or "",
                "status": args.status or "",
                "limit": args.limit,
            }
            res = requests.get(f"{base}/projects/{pid}/inbox/outbox", params=params, timeout=10)
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ outbox receipts failed: {e}")
