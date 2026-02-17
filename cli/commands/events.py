"""CLI unified events command handlers."""
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


def cmd_events(args):
    base = get_base_url()
    pid = _pid(args)
    if args.subcommand == "submit":
        payload = json.loads(args.payload) if args.payload else {}
        req = {
            "project_id": pid,
            "domain": args.domain,
            "event_type": args.type,
            "priority": args.priority,
            "payload": payload,
            "dedupe_key": args.dedupe_key,
            "max_attempts": args.max_attempts,
        }
        res = requests.post(f"{base}/events/submit", json=req, timeout=10)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        return
    if args.subcommand == "list":
        params = {
            "project_id": pid,
            "domain": args.domain or "",
            "event_type": args.type or "",
            "state": args.state or "",
            "agent_id": args.agent or "",
            "limit": args.limit,
        }
        res = requests.get(f"{base}/events", params=params, timeout=10)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        return
    if args.subcommand == "retry":
        res = requests.post(f"{base}/events/{args.event_id}/retry", json={"project_id": pid}, timeout=10)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        return
    if args.subcommand == "ack":
        res = requests.post(f"{base}/events/{args.event_id}/ack", json={"project_id": pid}, timeout=10)
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        return
    if args.subcommand == "reconcile":
        res = requests.post(
            f"{base}/events/reconcile",
            json={"project_id": pid, "timeout_sec": int(args.timeout_sec)},
            timeout=10,
        )
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        return

