"""CLI Angelia event queue command handlers."""
from __future__ import annotations

import json

import requests

from cli.utils import get_base_url


def _pid(args) -> str:
    base = get_base_url()
    try:
        cfg = requests.get(f"{base}/config", timeout=3).json()
        return args.project or cfg.get("current_project", "default")
    except Exception:
        return args.project or "default"


def cmd_angelia(args):
    base = get_base_url()
    pid = _pid(args)

    if args.subcommand == "enqueue":
        payload = json.loads(args.payload) if args.payload else {}
        raw_type = str(args.type or "").strip().lower() or "manual"
        if raw_type not in {"timer", "manual", "system"}:
            raise SystemExit("--type 仅支持: timer|manual|system")
        req = {
            "project_id": pid,
            "domain": "angelia",
            "event_type": raw_type,
            "priority": args.priority,
            "payload": {"agent_id": args.agent, **payload},
            "dedupe_key": args.dedupe_key,
        }
        res = requests.post(f"{base}/events/submit", json=req, timeout=10)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "events":
        raw_type = str(args.type or "").strip().lower()
        if raw_type and raw_type not in {"timer", "manual", "system"}:
            raise SystemExit("--type 仅支持: timer|manual|system")
        params = {
            "project_id": pid,
            "domain": "angelia",
            "agent_id": args.agent or "",
            "state": args.state or "",
            "event_type": raw_type or "",
            "limit": args.limit,
        }
        res = requests.get(f"{base}/events", params=params, timeout=10)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "agents":
        res = requests.get(f"{base}/angelia/agents/status", params={"project_id": pid}, timeout=10)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "retry":
        res = requests.post(
            f"{base}/events/{args.event_id}/retry",
            json={"project_id": pid},
            timeout=10,
        )
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))

    elif args.subcommand == "timer-tick":
        res = requests.post(f"{base}/angelia/timer/tick", json={"project_id": pid}, timeout=10)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))
