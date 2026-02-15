"""CLI detach background jobs command handlers."""
from __future__ import annotations

import json

import requests

from cli.utils import get_base_url


def cmd_detach(args):
    base = get_base_url()
    try:
        cfg = requests.get(f"{base}/config", timeout=3).json()
        pid = args.project or cfg.get("current_project", "default")
    except Exception:
        pid = args.project or "default"

    if args.subcommand == "submit":
        payload = {"agent_id": args.agent, "command": args.cmd}
        try:
            res = requests.post(f"{base}/projects/{pid}/detach/submit", json=payload, timeout=20)
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ detach submit failed: {e}")

    elif args.subcommand == "list":
        params = {
            "agent_id": args.agent or "",
            "status": args.status or "",
            "limit": args.limit,
        }
        try:
            res = requests.get(f"{base}/projects/{pid}/detach/jobs", params=params, timeout=10)
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ detach list failed: {e}")

    elif args.subcommand == "stop":
        try:
            res = requests.post(f"{base}/projects/{pid}/detach/jobs/{args.job_id}/stop", timeout=10)
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ detach stop failed: {e}")

    elif args.subcommand == "logs":
        try:
            res = requests.get(f"{base}/projects/{pid}/detach/jobs/{args.job_id}/logs", timeout=10)
            print((res.json() or {}).get("tail", ""))
        except Exception as e:
            print(f"❌ detach logs failed: {e}")
