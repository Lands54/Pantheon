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
        payload = {
            "project_id": pid,
            "domain": "runtime",
            "event_type": "detach_submitted_event",
            "payload": {"agent_id": args.agent, "command": args.cmd},
        }
        try:
            res = requests.post(f"{base}/events/submit", json=payload, timeout=20)
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ detach submit failed: {e}")

    elif args.subcommand == "list":
        params = {
            "project_id": pid,
            "domain": "runtime",
            "event_type": "detach_submitted_event",
            "agent_id": args.agent or "",
            "limit": args.limit,
        }
        if args.status:
            params["state"] = args.status
        try:
            res = requests.get(f"{base}/events", params=params, timeout=10)
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ detach list failed: {e}")

    elif args.subcommand == "stop":
        try:
            res = requests.post(
                f"{base}/events/submit",
                json={
                    "project_id": pid,
                    "domain": "runtime",
                    "event_type": "detach_stopping_event",
                    "payload": {"job_id": args.job_id},
                },
                timeout=10,
            )
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ detach stop failed: {e}")

    elif args.subcommand == "logs":
        try:
            res = requests.get(
                f"{base}/events",
                params={
                    "project_id": pid,
                    "domain": "runtime",
                    "agent_id": "",
                    "limit": 200,
                },
                timeout=10,
            )
            rows = (res.json() or {}).get("items", [])
            rows = [r for r in rows if str((r.get("payload") or {}).get("job_id", "")) == str(args.job_id)]
            print(json.dumps({"project_id": pid, "job_id": args.job_id, "items": rows[-20:]}, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ detach logs failed: {e}")
