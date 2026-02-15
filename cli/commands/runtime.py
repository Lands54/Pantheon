"""CLI runtime container command handlers."""
from __future__ import annotations

import json

import requests

from cli.utils import get_base_url


def cmd_runtime(args):
    base = get_base_url()
    try:
        cfg = requests.get(f"{base}/config", timeout=3).json()
        pid = args.project or cfg.get("current_project", "default")
    except Exception:
        pid = args.project or "default"

    if args.subcommand == "status":
        try:
            res = requests.get(f"{base}/projects/{pid}/runtime/agents", timeout=10)
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ runtime status failed: {e}")

    elif args.subcommand == "restart":
        try:
            res = requests.post(f"{base}/projects/{pid}/runtime/agents/{args.agent}/restart", timeout=10)
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ runtime restart failed: {e}")

    elif args.subcommand == "reconcile":
        try:
            res = requests.post(f"{base}/projects/{pid}/runtime/reconcile", timeout=20)
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ runtime reconcile failed: {e}")
