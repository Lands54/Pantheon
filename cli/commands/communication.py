"""CLI communication command handlers."""
from __future__ import annotations

import json
import requests

from cli.utils import get_base_url


def cmd_broadcast(args):
    pid = args.project or requests.get(f"{get_base_url()}/config").json().get("current_project")
    print(f"📢 BROADCASTING in {pid}: {args.message}")
    try:
        payload = {"message": args.message}
        old_res = requests.get(f"{get_base_url()}/config").json()
        old_pid = old_res.get("current_project")
        if pid != old_pid:
            old_res["current_project"] = pid
            requests.post(f"{get_base_url()}/config/save", json=old_res)

        with requests.post(f"{get_base_url()}/broadcast", json=payload, stream=True) as r:
            for line in r.iter_lines():
                if line:
                    line_str = line.decode("utf-8")
                    if line_str.startswith("data: "):
                        data = json.loads(line_str[6:])
                        if "content" in data:
                            speaker = (data.get("speaker") or "system").upper()
                            print(f"[{speaker}]: {data['content']}")

        if pid != old_pid:
            old_res["current_project"] = old_pid
            requests.post(f"{get_base_url()}/config/save", json=old_res)
    except Exception as e:
        print(f"❌ Broadcast failed: {e}")


def cmd_confess(args):
    try:
        payload = {"agent_id": args.id, "title": args.title, "message": args.message, "silent": args.silent}
        res = requests.post(f"{get_base_url()}/confess", json=payload)
        print(f"🤫 {res.json().get('status', 'Confession delivered.')}")
    except Exception:
        print("❌ Server error.")


def cmd_prayers(args):
    try:
        res = requests.get(f"{get_base_url()}/prayers/check")
        prayers = res.json().get("prayers", [])
        for p in prayers:
            print(f"[{p.get('from')}]: {p.get('content')}")
    except Exception:
        print("❌ Server error.")
