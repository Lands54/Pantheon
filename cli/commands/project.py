"""CLI project command handlers."""
from __future__ import annotations

import json
import requests

from cli.utils import get_base_url


def cmd_project(args):
    """Manage Projects."""
    base_url = get_base_url()
    if args.subcommand == "list":
        try:
            res = requests.get(f"{base_url}/config")
            data = res.json()
            print("\n🌍 SACRED WORLDS")
            current = data.get("current_project")
            for pid, _ in data["projects"].items():
                marker = "⭐" if pid == current else "  "
                print(f"{marker} {pid}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "create":
        try:
            payload = {"id": args.id}
            res = requests.post(f"{base_url}/projects/create", json=payload)
            if res.status_code == 200:
                print(f"✨ World '{args.id}' manifested.")
            else:
                print(f"❌ Failed: {res.json().get('error', 'Unknown error')}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "delete":
        try:
            res = requests.delete(f"{base_url}/projects/{args.id}")
            if res.status_code == 200:
                print(f"🗑️  World '{args.id}' collapsed and removed from existence.")
            else:
                print(f"❌ Failed: {res.json().get('detail', 'Unknown error')}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "switch":
        try:
            res = requests.get(f"{base_url}/config")
            data = res.json()
            if args.id not in data["projects"]:
                print(f"❌ World '{args.id}' does not exist.")
                return
            data["current_project"] = args.id
            requests.post(f"{base_url}/config/save", json=data)
            print(f"🌌 Shifted consciousness to world: {args.id}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "graph":
        try:
            res = requests.post(f"{base_url}/projects/{args.id}/knowledge/rebuild")
            if res.status_code == 200:
                data = res.json()
                print(f"🧠 Knowledge graph rebuilt for '{args.id}'")
                print(f"   Nodes: {data.get('nodes', 0)}")
                print(f"   Edges: {data.get('edges', 0)}")
                print(f"   Output: {data.get('output')}")
            else:
                print(f"❌ Failed: {res.json().get('detail', 'Unknown error')}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "start":
        try:
            res = requests.post(f"{base_url}/projects/{args.id}/start")
            if res.status_code == 200:
                data = res.json()
                print(f"🟢 Project started: {data.get('project_id')}")
                print(f"   Current Project: {data.get('current_project')}")
            else:
                detail = res.json().get("detail", "Unknown error")
                if res.status_code == 503 and "Docker unavailable" in str(detail):
                    print(f"❌ Failed to start project '{args.id}': {detail}")
                    print("   Project has been auto-stopped for safety.")
                    print("   Suggested next steps:")
                    print("   1) Start Docker Desktop / docker daemon")
                    print(f"   2) Retry: ./temple.sh project start {args.id}")
                    print(f"   3) Or switch backend: ./temple.sh -p {args.id} config set command_executor local")
                else:
                    print(f"❌ Failed: {detail}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "stop":
        try:
            res = requests.post(f"{base_url}/projects/{args.id}/stop")
            if res.status_code == 200:
                data = res.json()
                print(f"🔴 Project stopped: {data.get('project_id')}")
                print(f"   Current Project: {data.get('current_project')}")
            else:
                print(f"❌ Failed: {res.json().get('detail', 'Unknown error')}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "report":
        try:
            # Build report writes both project-local artifacts and Mnemosyne human archive entry.
            res = requests.post(f"{base_url}/projects/{args.id}/report/build")
            if res.status_code == 200:
                data = res.json()
                print(f"🧾 Project report built: {data.get('project_id')}")
                output = data.get("output", {})
                print(f"   JSON: {output.get('json')}")
                print(f"   MD: {output.get('md')}")
                if output.get("mirror_md"):
                    print(f"   Mirror: {output.get('mirror_md')}")
                print(f"   Mnemosyne Entry: {data.get('mnemosyne_entry_id')}")
            else:
                print(f"❌ Failed: {res.json().get('detail', 'Unknown error')}")
        except Exception:
            print("❌ Server error.")

    elif args.subcommand == "report-show":
        try:
            res = requests.get(f"{base_url}/projects/{args.id}/report")
            if res.status_code == 200:
                print(json.dumps(res.json(), ensure_ascii=False, indent=2))
            else:
                print(f"❌ Failed: {res.json().get('detail', 'Unknown error')}")
        except Exception:
            print("❌ Server error.")
