"""CLI communication command handlers."""
from __future__ import annotations

import requests

from cli.utils import get_base_url


def cmd_confess(args):
    try:
        payload = {"agent_id": args.id, "title": args.title, "message": args.message, "silent": args.silent}
        res = requests.post(f"{get_base_url()}/confess", json=payload)
        print(f"🤫 {res.json().get('status', 'Confession delivered.')}")
    except Exception:
        print("❌ Server error.")
