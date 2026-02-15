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
from cli.commands.check import cmd_check
from cli.commands.protocol import cmd_protocol
from cli.commands.mnemosyne import cmd_mnemosyne
from cli.commands.project import cmd_project as cmd_project_v2
from cli.commands.agent import cmd_agent as cmd_agent_v2
from cli.commands.communication import (
    cmd_broadcast as cmd_broadcast_v2,
    cmd_confess as cmd_confess_v2,
    cmd_prayers as cmd_prayers_v2,
)
from cli.utils import get_base_url

CONFIG_PATH = Path("config.json")

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4)

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
    cmd_project_v2(args)

def cmd_agent(args):
    cmd_agent_v2(args)

def cmd_broadcast(args):
    cmd_broadcast_v2(args)

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
                        content = data.get("content", "")
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

    # check
    p_check = subparsers.add_parser("check", help="Check agent's recent activity and responses")
    p_check.add_argument("agent_id", help="Agent ID to check")

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
    p_proj_graph = proj_sub.add_parser("graph", help="Rebuild project knowledge graph")
    p_proj_graph.add_argument("id")
    p_proj_start = proj_sub.add_parser("start", help="Start project simulation (exclusive active project)")
    p_proj_start.add_argument("id")
    p_proj_stop = proj_sub.add_parser("stop", help="Stop project simulation")
    p_proj_stop.add_argument("id")
    p_proj_report = proj_sub.add_parser("report", help="Build project report and archive to Mnemosyne human vault")
    p_proj_report.add_argument("id")
    p_proj_report_show = proj_sub.add_parser("report-show", help="Show latest built project report JSON")
    p_proj_report_show.add_argument("id")

    # protocol (Hermes bus)
    p_protocol = subparsers.add_parser("protocol", help="Hermes protocol bus operations")
    proto_sub = p_protocol.add_subparsers(dest="subcommand")
    proto_sub.add_parser("list", help="List registered protocols")
    p_proto_register = proto_sub.add_parser("register", help="Register executable protocol")
    p_proto_register.add_argument("--name", required=True)
    p_proto_register.add_argument("--description", default="")
    p_proto_register.add_argument("--mode", choices=["sync", "async", "both"], default="both")
    p_proto_register.add_argument("--provider", choices=["agent_tool", "http"], default="http")
    p_proto_register.add_argument("--owner-agent", default="", help="Routing owner agent id")
    p_proto_register.add_argument("--agent", help="Provider agent id (agent_tool)")
    p_proto_register.add_argument("--tool", help="Provider tool name (agent_tool)")
    p_proto_register.add_argument("--url", help="Provider URL (http)")
    p_proto_register.add_argument("--method", default="POST", help="Provider HTTP method (http)")
    p_proto_register.add_argument("--request-schema", default='{\"type\":\"object\"}')
    p_proto_register.add_argument("--response-schema", default='{\"type\":\"object\",\"required\":[\"result\"],\"properties\":{\"result\":{\"type\":\"string\"}}}')
    p_proto_register.add_argument("--max-concurrency", type=int, default=2)
    p_proto_register.add_argument("--rate-per-minute", type=int, default=60)
    p_proto_register.add_argument("--timeout", type=int, default=30)
    p_proto_call = proto_sub.add_parser("call", help="Invoke protocol")
    p_proto_call.add_argument("--name", required=True)
    p_proto_call.add_argument("--mode", choices=["sync", "async"], default="sync")
    p_proto_call.add_argument("--caller", required=True)
    p_proto_call.add_argument("--payload", default="{}")
    p_proto_route = proto_sub.add_parser("route", help="Route call by target agent + function id")
    p_proto_route.add_argument("--target", required=True, help="Target agent id")
    p_proto_route.add_argument("--function", required=True, help="Function id")
    p_proto_route.add_argument("--caller", required=True)
    p_proto_route.add_argument("--mode", choices=["sync", "async"], default="sync")
    p_proto_route.add_argument("--payload", default="{}")
    p_proto_job = proto_sub.add_parser("job", help="Check async job status")
    p_proto_job.add_argument("job_id")
    p_proto_history = proto_sub.add_parser("history", help="Show invocation history")
    p_proto_history.add_argument("--name", default="")
    p_proto_history.add_argument("--limit", type=int, default=20)
    p_contract_register = proto_sub.add_parser("contract-register", help="Register contract JSON")
    p_contract_register.add_argument("--file", required=True, help="Path to contract json file")
    p_contract_commit = proto_sub.add_parser("contract-commit", help="Commit to contract")
    p_contract_commit.add_argument("--title", required=True)
    p_contract_commit.add_argument("--version", required=True)
    p_contract_commit.add_argument("--agent", required=True)
    p_contract_resolve = proto_sub.add_parser("contract-resolve", help="Resolve contract obligations")
    p_contract_resolve.add_argument("--title", required=True)
    p_contract_resolve.add_argument("--version", required=True)
    p_contract_list = proto_sub.add_parser("contract-list", help="List contracts")
    p_contract_list.add_argument("--include-disabled", action="store_true")
    p_contract_disable = proto_sub.add_parser("contract-disable", help="Exit commitment; auto-disable when no committers remain")
    p_contract_disable.add_argument("--title", required=True)
    p_contract_disable.add_argument("--version", required=True)
    p_contract_disable.add_argument("--agent", required=True)
    p_contract_disable.add_argument("--reason", default="")
    p_clause_tpl = proto_sub.add_parser("clause-template", help="Generate executable contract clause JSON template")
    p_clause_tpl.add_argument("--id", required=True, help="Clause/function id")
    p_clause_tpl.add_argument("--summary", default="")
    p_clause_tpl.add_argument("--owner-agent", default="", help="Owner agent id for this clause")
    p_clause_tpl.add_argument("--provider", choices=["http", "agent_tool"], default="http")
    p_clause_tpl.add_argument("--url", default="", help="Provider URL (http)")
    p_clause_tpl.add_argument("--method", default="POST", help="Provider HTTP method (http)")
    p_clause_tpl.add_argument("--agent", default="", help="Provider agent id (agent_tool)")
    p_clause_tpl.add_argument("--tool", default="", help="Provider tool name (agent_tool)")
    p_clause_tpl.add_argument("--mode", choices=["sync", "async", "both"], default="both")
    p_clause_tpl.add_argument("--timeout", type=int, default=30)
    p_clause_tpl.add_argument("--rate", type=int, default=60)
    p_clause_tpl.add_argument("--concurrency", type=int, default=2)
    p_clause_tpl.add_argument("--request-schema", default='{"type":"object"}')
    p_clause_tpl.add_argument("--response-schema", default='{"type":"object"}')
    p_port_reserve = proto_sub.add_parser("port-reserve", help="Reserve a local port lease")
    p_port_reserve.add_argument("--owner", required=True)
    p_port_reserve.add_argument("--preferred", type=int, default=0)
    p_port_reserve.add_argument("--min", dest="min_port", type=int, default=12000)
    p_port_reserve.add_argument("--max", dest="max_port", type=int, default=19999)
    p_port_reserve.add_argument("--note", default="")
    p_port_release = proto_sub.add_parser("port-release", help="Release port lease(s)")
    p_port_release.add_argument("--owner", required=True)
    p_port_release.add_argument("--port", type=int, default=0)
    proto_sub.add_parser("port-list", help="List leased ports")

    # mnemosyne archives
    p_mn = subparsers.add_parser("mnemosyne", help="Mnemosyne archive operations")
    mn_sub = p_mn.add_subparsers(dest="subcommand")
    p_mn_write = mn_sub.add_parser("write", help="Write archive entry")
    p_mn_write.add_argument("--vault", choices=["agent", "human", "system"], default="human")
    p_mn_write.add_argument("--author", default="human")
    p_mn_write.add_argument("--title", required=True)
    p_mn_write.add_argument("--content", required=True)
    p_mn_write.add_argument("--tags", default="")
    p_mn_list = mn_sub.add_parser("list", help="List archive entries")
    p_mn_list.add_argument("--vault", choices=["agent", "human", "system"], default="human")
    p_mn_list.add_argument("--limit", type=int, default=20)
    p_mn_read = mn_sub.add_parser("read", help="Read one archive entry")
    p_mn_read.add_argument("entry_id")
    p_mn_read.add_argument("--vault", choices=["agent", "human", "system"], default="human")

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
    p_cf.add_argument("--silent", action="store_true", help="Send message without triggering an immediate pulse")
    
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
    if args.command == "protocol" and not args.subcommand:
        p_protocol.print_help()
        sys.exit(0)
    if args.command == "mnemosyne" and not args.subcommand:
        p_mn.print_help()
        sys.exit(0)
    
    if args.command == "init": cmd_init(args)
    elif args.command == "list": cmd_list(args)
    elif args.command == "check": cmd_check(args)
    elif args.command == "config": cmd_config(args)
    elif args.command == "project": cmd_project(args)
    elif args.command == "protocol": cmd_protocol(args)
    elif args.command == "mnemosyne": cmd_mnemosyne(args)
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
        cmd_confess_v2(args)
    elif args.command == "prayers":
        cmd_prayers_v2(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
