"""CLI agent command handlers."""
from __future__ import annotations

import sys
from pathlib import Path


def cmd_agent(args):
    """View or edit Agent directives."""
    pid = args.project or "default"
    agent_file = Path(f"projects/{pid}/mnemosyne/agent_profiles/{args.id}.md")

    if not agent_file.exists():
        print(f"❌ Being '{args.id}' not found in world '{pid}'.")
        return

    if args.subcommand == "view":
        print(f"--- DIRECTIVES FOR {args.id} IN {pid} ---")
        print(agent_file.read_text(encoding="utf-8"))
    elif args.subcommand == "edit":
        print(f"📝 Enter new directives for {args.id} (End with Ctrl-D/Ctrl-Z):")
        new_directives = sys.stdin.read()
        if new_directives.strip():
            agent_file.write_text(new_directives, encoding="utf-8")
            print(f"✅ Directives for {args.id} updated.")
        else:
            print("🚫 Canceled.")
