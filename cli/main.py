"""
Gods Temple CLI - Sacred Command Interface
A high-efficiency tool for managing the divine system.
"""
import argparse
import sys
import json
import requests
import os
from pathlib import Path
from typing import Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli.commands.config import cmd_config

CONFIG_PATH = Path("config.json")

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4)

def get_base_url():
    return "http://localhost:8000"

def get_current_project(config):
    return config.get("current_project", "default")

def sync_server(data):
    try:
        requests.post(f"{get_base_url()}/config/save", json=data, timeout=2)
        return True
    except:
        return False

# --- Command Handlers ---

def cmd_init(args):
    """Set the sacred access key"""
    config = load_config()
    config["openrouter_api_key"] = args.key
    save_config(config)
    print(f"✅ Sacred Access Key enshrined.")
    if sync_server(config):
        print("🚀 Synchronized with living server.")
    else:
        print("⚠️  Server not reachable. Saved to disk only.")

def cmd_list(args):
    """List all Beings and Simulation Status"""
    try:
        res = requests.get(f"{get_base_url()}/config")
        data = res.json()
        pid = args.project or data.get("current_project", "default")
        proj = data["projects"].get(pid)
        
        if not proj:
            print(f"❌ Project '{pid}' not found.")
            return

        print(f"\n🏛  TEMPLE STATUS - Project: {pid} ({proj.get('name')})")
        print(f"API Key:   {'SET' if data['openrouter_api_key'] else 'MISSING'}")
        sim_status = "🟢 ON" if proj.get("simulation_enabled") else "🔴 OFF"
        print(f"Simulation: {sim_status} (Pulse: {proj.get('simulation_interval_min')}-{proj.get('simulation_interval_max')}s)")
        
        print("\n--- BEINGS ---")
        active = proj.get("active_agents", [])
        settings = proj.get("agent_settings", {})
        
        # Get agents for this project
        agents_res = requests.get(f"{get_base_url()}/config") # available_agents depends on current_project in server
        # We might need an endpoint for project-specific available agents if we want to list another project's agents
        # For now, let's assume we list current project's agents
        
        for agent in data["available_agents"]:
            status = "🟢 [ACTIVE]" if agent in active else "⚪ [LATENT]"
            model = settings.get(agent, {}).get("model", "default")
            print(f"{status} {agent:<12} | Model: {model}")
    except Exception as e:
        print(f"❌ Server error: {e}")

def cmd_project(args):
    """Manage Projects"""
    if args.subcommand == "list":
        try:
            res = requests.get(f"{get_base_url()}/config")
            data = res.json()
            print("\n🌍 SACRED WORLDS")
            current = data.get("current_project")
            for pid, proj in data["projects"].items():
                marker = "⭐" if pid == current else "  "
                print(f"{marker} {pid}")
        except:
            print("❌ Server error.")
    
    elif args.subcommand == "create":
        try:
            payload = {"id": args.id}
            res = requests.post(f"{get_base_url()}/projects/create", json=payload)
            if res.status_code == 200:
                print(f"✨ World '{args.id}' manifested.")
            else:
                print(f"❌ Failed: {res.json().get('error', 'Unknown error')}")
        except:
            print("❌ Server error.")
    
    elif args.subcommand == "delete":
        try:
            res = requests.delete(f"{get_base_url()}/projects/{args.id}")
            if res.status_code == 200:
                print(f"🗑️  World '{args.id}' collapsed and removed from existence.")
            else:
                print(f"❌ Failed: {res.json().get('detail', 'Unknown error')}")
        except:
            print("❌ Server error.")
    
    elif args.subcommand == "switch":
        try:
            res = requests.get(f"{get_base_url()}/config")
            data = res.json()
            if args.id not in data["projects"]:
                print(f"❌ World '{args.id}' does not exist.")
                return
            data["current_project"] = args.id
            requests.post(f"{get_base_url()}/config/save", json=data)
            print(f"🌌 Shifted consciousness to world: {args.id}")
        except:
            print("❌ Server error.")

def cmd_agent(args):
    """View or Edit Agent Directives"""
    # Note: This tool currently reads from disk, but with projects it should read from projects/{project_id}/agents/...
    config = load_config()
    pid = args.project or config.get("current_project", "default")
    agent_file = Path(f"projects/{pid}/agents/{args.id}/agent.md")
    
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

def cmd_broadcast(args):
    """Deliver a Sacred Decree"""
    pid = args.project or requests.get(f"{get_base_url()}/config").json().get("current_project")
    print(f"📢 BROADCASTING in {pid}: {args.message}")
    try:
        payload = {"message": args.message}
        # The /broadcast endpoint uses current_project. 
        # If we want to broadcast to a specific project, we should switch first or the endpoint should accept project_id.
        # Our server endpoint currently doesn't take project_id in the body, it uses runtime_config.current_project.
        
        # Switch if necessary
        old_res = requests.get(f"{get_base_url()}/config").json()
        old_pid = old_res.get("current_project")
        if pid != old_pid:
            old_res["current_project"] = pid
            requests.post(f"{get_base_url()}/config/save", json=old_res)

        with requests.post(f"{get_base_url()}/broadcast", json=payload, stream=True) as r:
            for line in r.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data = json.loads(line_str[6:])
                        if "content" in data:
                            print(f"[{data['speaker'].upper()}]: {data['content']}")
        
        # Switch back
        if pid != old_pid:
            old_res["current_project"] = old_pid
            requests.post(f"{get_base_url()}/config/save", json=old_res)
    except Exception as e:
        print(f"❌ Broadcast failed: {e}")

def cmd_test(args):
    """Run Automated Integration Tests"""
    import time
    test_id = f"test_world_{int(time.time())}"
    print(f"🧪 STARTING AUTOMATED DIVINE TEST: {test_id}")
    
    try:
        # 1. Create Project
        print("Step 1: Creating test world...")
        requests.post(f"{get_base_url()}/projects/create", json={"id": test_id, "name": "Testing Grounds"})
        
        # 2. Verify creation
        config = requests.get(f"{get_base_url()}/config").json()
        if test_id not in config["projects"]:
            print("❌ FAILED: World not found in config.")
            return

        # 3. Switch to project
        print("Step 2: Switching to test world...")
        config["current_project"] = test_id
        # Activate genesis
        config["projects"][test_id]["active_agents"] = ["genesis"]
        requests.post(f"{get_base_url()}/config/save", json=config)

        # 4. Create another agent
        print("Step 3: Invoking specialized agent (tester)...")
        requests.post(f"{get_base_url()}/agents/create", json={
            "agent_id": "tester",
            "directives": "# TESTER\nYour goal is to reply with 'MANIFEST_SUCCESS' if you receive a test signal."
        })
        
        # 5. Activate tester
        config = requests.get(f"{get_base_url()}/config").json()
        config["projects"][test_id]["active_agents"].append("tester")
        requests.post(f"{get_base_url()}/config/save", json=config)

        # 6. Broadcast and check responses
        print("Step 4: Running broadcast integration...")
        received_success = False
        payload = {"message": "Divine Test Signal: Please respond."}
        with requests.post(f"{get_base_url()}/broadcast", json=payload, stream=True) as r:
            for line in r.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data = json.loads(line_str[6:])
                        speaker = data.get("speaker", "").upper()
                        content = data.get("content", "")
                        print(f"   [{speaker}]: {content[:50]}...")
                        if "MANIFEST_SUCCESS" in content:
                            received_success = True
        
        if received_success:
            print("\n✅ TEST PASSED: Agent communication verified.")
        else:
            print("\n⚠️  TEST PARTIAL: Agent responded but trigger word missing.")

        # 7. Cleanup
        if args.cleanup:
            print("Step 5: Cleaning up test world...")
            # Use the new server-side project deletion endpoint
            requests.delete(f"{get_base_url()}/projects/{test_id}")
            print("✅ Cleanup complete.")
            
    except Exception as e:
        print(f"❌ TEST FAILED with error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Temple CLI - Manage the Gods Platform")
    parser.add_argument("--project", "-p", help="Specific project to operate on")
    subparsers = parser.add_subparsers(dest="command")

    # init
    p_init = subparsers.add_parser("init", help="Enshrine API Key")
    p_init.add_argument("key")

    # list
    subparsers.add_parser("list", help="List agents in current project")

    # config
    p_config = subparsers.add_parser("config", help="Manage configuration")
    config_sub = p_config.add_subparsers(dest="subcommand")
    config_sub.add_parser("show", help="Show current configuration")
    p_config_set = config_sub.add_parser("set", help="Set configuration value")
    p_config_set.add_argument("key", help="Config key (e.g., simulation.enabled, agent.genesis.model)")
    p_config_set.add_argument("value", help="Config value")
    config_sub.add_parser("models", help="List available models")

    # Project management
    p_proj = subparsers.add_parser("project", help="Manage Worlds (Projects)")
    proj_sub = p_proj.add_subparsers(dest="subcommand")
    proj_sub.add_parser("list", help="List all worlds")
    p_proj_create = proj_sub.add_parser("create", help="Create a new world")
    p_proj_create.add_argument("id", help="The name/ID of the world")
    p_proj_switch = proj_sub.add_parser("switch", help="Switch current world")
    p_proj_switch.add_argument("id")
    p_proj_delete = proj_sub.add_parser("delete", help="Delete a world")
    p_proj_delete.add_argument("id")

    # activate / deactivate
    subparsers.add_parser("activate").add_argument("id")
    subparsers.add_parser("deactivate").add_argument("id")

    # agent [view/edit]
    p_agent = subparsers.add_parser("agent")
    p_agent.add_argument("subcommand", choices=["view", "edit"])
    p_agent.add_argument("id")

    # broadcast
    p_bc = subparsers.add_parser("broadcast")
    p_bc.add_argument("message")
    
    # confess
    p_cf = subparsers.add_parser("confess")
    p_cf.add_argument("id")
    p_cf.add_argument("message")
    
    # prayers
    subparsers.add_parser("prayers")

    # test
    p_test = subparsers.add_parser("test", help="Run automated integration tests")
    p_test.add_argument("--cleanup", action="store_true", help="Delete test project after completion")

    # help
    p_help = subparsers.add_parser("help", help="Show this help message or help for a specific command")
    p_help.add_argument("cmd", nargs="?", help="Specific command to show help for")

    args = parser.parse_args()

    if args.command == "help":
        if args.cmd:
            # Try to find the subparser for the requested command
            sub_parsers_actions = [
                action for action in parser._actions 
                if isinstance(action, argparse._SubParsersAction)
            ]
            for action in sub_parsers_actions:
                if args.cmd in action.choices:
                    action.choices[args.cmd].print_help()
                    sys.exit(0)
        parser.print_help()
        sys.exit(0)
    
    if args.command == "project" and not args.subcommand:
        p_proj.print_help()
        sys.exit(0)
    
    if args.command == "init": cmd_init(args)
    elif args.command == "list": cmd_list(args)
    elif args.command == "config": cmd_config(args)
    elif args.command == "project": cmd_project(args)
    elif args.command == "agent": cmd_agent(args)
    elif args.command == "broadcast": cmd_broadcast(args)
    elif args.command == "test": cmd_test(args)
    elif args.command == "activate":
        try:
            res = requests.get(f"{get_base_url()}/config").json()
            pid = args.project or res.get("current_project", "default")
            proj = res["projects"].get(pid)
            if args.id not in proj["active_agents"]:
                proj["active_agents"].append(args.id)
                requests.post(f"{get_base_url()}/config/save", json=res)
                print(f"✨ {args.id} activated in {pid}.")
        except: print("❌ Server error.")
    elif args.command == "deactivate":
        try:
            res = requests.get(f"{get_base_url()}/config").json()
            pid = args.project or res.get("current_project", "default")
            proj = res["projects"].get(pid)
            if args.id in proj["active_agents"]:
                proj["active_agents"].remove(args.id)
                requests.post(f"{get_base_url()}/config/save", json=res)
                print(f"🌘 {args.id} deactivated in {pid}.")
        except: print("❌ Server error.")
    elif args.command == "confess":
        try:
            payload = {"agent_id": args.id, "message": args.message}
            requests.post(f"{get_base_url()}/confess", json=payload)
            print(f"🤫 Confession delivered to {args.id}.")
        except: print("❌ Server error.")
    elif args.command == "prayers":
        try:
            res = requests.get(f"{get_base_url()}/prayers/check")
            prayers = res.json().get("prayers", [])
            for p in prayers:
                print(f"[{p.get('from')}]: {p.get('content')}")
        except: print("❌ Server error.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
