"""CLI context observability commands (Janus)."""
from __future__ import annotations

import json

import requests

from cli.utils import get_base_url


def cmd_context(args):
    base = get_base_url()
    try:
        cfg = requests.get(f"{base}/config", timeout=3).json()
        pid = args.project or cfg.get("current_project", "default")
    except Exception:
        pid = args.project or "default"

    if args.subcommand == "preview":
        try:
            res = requests.get(
                f"{base}/projects/{pid}/context/preview",
                params={"agent_id": args.agent},
                timeout=10,
            )
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ context preview failed: {e}")

    elif args.subcommand == "reports":
        try:
            res = requests.get(
                f"{base}/projects/{pid}/context/reports",
                params={"agent_id": args.agent, "limit": args.limit},
                timeout=10,
            )
            print(json.dumps(res.json(), ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"❌ context reports failed: {e}")
