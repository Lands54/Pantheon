"""
Gods Temple CLI - Sacred Command Interface
A high-efficiency tool for managing the divine system.
"""
import argparse
import json
import requests
import os
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli.commands.config import cmd_config
from cli.commands.check import cmd_check
from cli.commands.protocol import cmd_protocol
from cli.commands.mnemosyne import cmd_mnemosyne
from cli.commands.runtime import cmd_runtime
from cli.commands.detach import cmd_detach
from cli.commands.context import cmd_context
from cli.commands.inbox import cmd_inbox
from cli.commands.angelia import cmd_angelia
from cli.commands.events import cmd_events
from cli.commands.msg import cmd_msg
from cli.commands.project import cmd_project as cmd_project_v2
from cli.commands.agent import cmd_agent as cmd_agent_v2
from cli.commands.doctor import cmd_doctor
from cli.utils import get_base_url
from gods.identity import HUMAN_AGENT_ID

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

def cmd_project(args):
    cmd_project_v2(args)

def cmd_agent(args):
    cmd_agent_v2(args)

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
        config["projects"][test_id]["active_agents"] = []
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

        # 6. Interaction message submit and check outbox
        print("Step 4: Running interaction-message pipeline integration...")
        send_res = requests.post(
            f"{get_base_url()}/events/submit",
            json={
                "project_id": test_id,
                "domain": "interaction",
                "event_type": "interaction.message.sent",
                "payload": {
                    "to_id": "tester",
                    "sender_id": HUMAN_AGENT_ID,
                    "title": "Divine Test Signal",
                    "content": "Please respond with MANIFEST_SUCCESS in your next pulse.",
                    "msg_type": "confession",
                    "trigger_pulse": True,
                },
            },
        )
        ok = send_res.status_code == 200
        outbox_res = requests.get(
            f"{get_base_url()}/projects/{test_id}/inbox/outbox",
            params={"from_agent_id": HUMAN_AGENT_ID, "to_agent_id": "tester", "limit": 20},
        )
        rows = (outbox_res.json() or {}).get("items", []) if outbox_res.status_code == 200 else []
        ok = ok and any(str(x.get("title", "")) == "Divine Test Signal" for x in rows)

        if ok:
            print("\n✅ TEST PASSED: Confess communication verified.")
        else:
            print("\n⚠️  TEST PARTIAL: Confess accepted but outbox record not confirmed.")

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

    # check
    p_check = subparsers.add_parser("check", help="Check agent's recent activity and responses")
    p_check.add_argument("agent_id", help="Agent ID to check")

    # doctor
    p_doctor = subparsers.add_parser("doctor", help="Auto-repair project and run readiness checks")
    p_doctor.add_argument("--project", "-p", dest="project", default="", help="Project ID (default: current project)")
    p_doctor.add_argument("--skip-guards", action="store_true", help="Skip repository guard scripts")
    p_doctor.add_argument("--strict", action="store_true", help="Treat guard script failures as blocking")

    # msg (human friendly interaction commands)
    p_msg = subparsers.add_parser("msg", help="Human-friendly interaction commands")
    msg_sub = p_msg.add_subparsers(dest="subcommand")
    p_msg_send = msg_sub.add_parser("send", help="Send a message to an agent")
    p_msg_send.add_argument("--to", required=True, help="Target agent id")
    p_msg_send.add_argument("--title", required=True)
    p_msg_send.add_argument("--content", required=True)
    p_msg_send.add_argument("--sender", default=HUMAN_AGENT_ID, help=f"Sender agent id (default: {HUMAN_AGENT_ID})")
    p_msg_send.add_argument("--msg-type", default="confession")
    p_msg_send.add_argument("--no-pulse", action="store_true", help="Do not trigger immediate pulse")
    p_msg_send.add_argument("--max-attempts", type=int, default=3)

    # config
    p_config = subparsers.add_parser("config", help="Manage configuration")
    config_sub = p_config.add_subparsers(dest="subcommand")
    config_sub.add_parser("show", help="Show current configuration")
    p_config_set = config_sub.add_parser("set", help="Set configuration value")
    p_config_set.add_argument(
        "key",
        help=(
            "Config key (e.g., simulation.enabled, agent.genesis.model, "
            "agent.genesis.disabled_tools, agent.genesis.disable_tool, agent.genesis.enable_tool)"
        ),
    )
    p_config_set.add_argument("value", help="Config value")
    config_sub.add_parser("models", help="List available models")
    p_config_check_mem = config_sub.add_parser("check-memory-policy", help="Validate strict Mnemosyne memory policy")
    p_config_check_mem.add_argument("--project", default="", help="Project ID (default: current project)")

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

    # runtime container ops
    p_rt = subparsers.add_parser("runtime", help="Runtime container operations")
    rt_sub = p_rt.add_subparsers(dest="subcommand")
    rt_sub.add_parser("status", help="Show per-agent runtime container status")
    p_rt_restart = rt_sub.add_parser("restart", help="Restart one agent runtime container")
    p_rt_restart.add_argument("agent")
    rt_sub.add_parser("reconcile", help="Reconcile runtime containers with active agents")

    # detach background jobs
    p_detach = subparsers.add_parser("detach", help="Detach background jobs")
    detach_sub = p_detach.add_subparsers(dest="subcommand")
    p_detach_submit = detach_sub.add_parser("submit", help="Submit detach job")
    p_detach_submit.add_argument("agent")
    p_detach_submit.add_argument("--cmd", required=True)
    p_detach_list = detach_sub.add_parser("list", help="List detach jobs")
    p_detach_list.add_argument("--agent", default="")
    p_detach_list.add_argument("--status", default="")
    p_detach_list.add_argument("--limit", type=int, default=50)
    p_detach_stop = detach_sub.add_parser("stop", help="Stop detach job")
    p_detach_stop.add_argument("job_id")
    p_detach_logs = detach_sub.add_parser("logs", help="Show detach job log tail")
    p_detach_logs.add_argument("job_id")

    # janus context observability
    p_ctx = subparsers.add_parser("context", help="Janus context observability")
    ctx_sub = p_ctx.add_subparsers(dest="subcommand")
    p_ctx_preview = ctx_sub.add_parser("preview", help="Show latest context preview for one agent")
    p_ctx_preview.add_argument("agent")
    p_ctx_reports = ctx_sub.add_parser("reports", help="List context build reports for one agent")
    p_ctx_reports.add_argument("agent")
    p_ctx_reports.add_argument("--limit", type=int, default=20)

    # inbox operations
    p_inbox = subparsers.add_parser("inbox", help="Inbox operations")
    inbox_sub = p_inbox.add_subparsers(dest="subcommand")
    p_inbox_outbox = inbox_sub.add_parser("outbox", help="Show outbox receipt records")
    p_inbox_outbox.add_argument("--agent", default="")
    p_inbox_outbox.add_argument("--to", default="")
    p_inbox_outbox.add_argument("--status", default="")
    p_inbox_outbox.add_argument("--limit", type=int, default=50)

    # angelia event loop operations
    p_ang = subparsers.add_parser("angelia", help="Angelia event queue and wakeup operations")
    ang_sub = p_ang.add_subparsers(dest="subcommand")
    p_ang_enqueue = ang_sub.add_parser("enqueue", help="Enqueue one event")
    p_ang_enqueue.add_argument("agent")
    p_ang_enqueue.add_argument("--type", default="manual")
    p_ang_enqueue.add_argument("--priority", type=int, default=None)
    p_ang_enqueue.add_argument("--payload", default="{}")
    p_ang_enqueue.add_argument("--dedupe-key", default="")
    p_ang_events = ang_sub.add_parser("events", help="List events")
    p_ang_events.add_argument("--agent", default="")
    p_ang_events.add_argument("--state", default="")
    p_ang_events.add_argument("--type", default="")
    p_ang_events.add_argument("--limit", type=int, default=50)
    ang_sub.add_parser("agents", help="Show agent runtime statuses")
    p_ang_wake = ang_sub.add_parser("wake", help="Wake one agent")
    p_ang_wake.add_argument("agent")
    p_ang_retry = ang_sub.add_parser("retry", help="Retry dead/failed event")
    p_ang_retry.add_argument("event_id")
    ang_sub.add_parser("timer-tick", help="Run one timer injection pass")

    # unified events operations
    p_ev = subparsers.add_parser("events", help="Unified event bus operations")
    ev_sub = p_ev.add_subparsers(dest="subcommand")
    p_ev_submit = ev_sub.add_parser("submit", help="Submit one event")
    p_ev_submit.add_argument("--domain", required=True)
    p_ev_submit.add_argument("--type", required=True)
    p_ev_submit.add_argument("--priority", type=int, default=None)
    p_ev_submit.add_argument("--payload", default="{}")
    p_ev_submit.add_argument("--dedupe-key", default="")
    p_ev_submit.add_argument("--max-attempts", type=int, default=3)
    p_ev_list = ev_sub.add_parser("list", help="List events")
    p_ev_list.add_argument("--domain", default="")
    p_ev_list.add_argument("--type", default="")
    p_ev_list.add_argument("--state", default="")
    p_ev_list.add_argument("--agent", default="")
    p_ev_list.add_argument("--limit", type=int, default=50)
    p_ev_retry = ev_sub.add_parser("retry", help="Retry dead/failed event")
    p_ev_retry.add_argument("event_id")
    p_ev_ack = ev_sub.add_parser("ack", help="Ack one event")
    p_ev_ack.add_argument("event_id")
    p_ev_reconcile = ev_sub.add_parser("reconcile", help="Reconcile stale processing events")
    p_ev_reconcile.add_argument("--timeout-sec", type=int, default=60)

    # agent operations
    p_agent = subparsers.add_parser("agent", help="Agent operations")
    agent_sub = p_agent.add_subparsers(dest="subcommand")
    agent_sub.add_parser("list", help="List agents in current project")
    p_agent_create = agent_sub.add_parser("create", help="Create one agent")
    p_agent_create.add_argument("id")
    p_agent_create.add_argument("--directives", required=True)
    p_agent_delete = agent_sub.add_parser("delete", help="Delete one agent")
    p_agent_delete.add_argument("id")
    p_agent_activate = agent_sub.add_parser("activate", help="Activate one agent")
    p_agent_activate.add_argument("id")
    p_agent_deactivate = agent_sub.add_parser("deactivate", help="Deactivate one agent")
    p_agent_deactivate.add_argument("id")
    p_agent_status = agent_sub.add_parser("status", help="Show scheduler/runtime status for agents")
    p_agent_status.add_argument("--agent-id", default="", help="Filter by one agent id")
    p_agent_status.add_argument("--json", action="store_true", help="Output raw JSON")
    p_agent_strategy = agent_sub.add_parser("strategy", help="Manage per-agent runtime strategy")
    p_agent_strategy_sub = p_agent_strategy.add_subparsers(dest="action")
    p_agent_strategy_get = p_agent_strategy_sub.add_parser("get", help="Get one agent strategy")
    p_agent_strategy_get.add_argument("--agent", required=True, help="Agent id")
    p_agent_strategy_set = p_agent_strategy_sub.add_parser("set", help="Set one agent strategy")
    p_agent_strategy_set.add_argument("--agent", required=True, help="Agent id")
    p_agent_strategy_set.add_argument("--strategy", required=True, choices=["react_graph", "freeform"])
    p_agent_strategy_sub.add_parser("list", help="List agent strategy overrides")
    p_agent_view = agent_sub.add_parser("view", help="View agent directives")
    p_agent_view.add_argument("id")
    p_agent_edit = agent_sub.add_parser("edit", help="Edit agent directives from stdin")
    p_agent_edit.add_argument("id")

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
    if args.command == "runtime" and not args.subcommand:
        p_rt.print_help()
        sys.exit(0)
    if args.command == "detach" and not args.subcommand:
        p_detach.print_help()
        sys.exit(0)
    if args.command == "context" and not args.subcommand:
        p_ctx.print_help()
        sys.exit(0)
    if args.command == "inbox" and not args.subcommand:
        p_inbox.print_help()
        sys.exit(0)
    if args.command == "angelia" and not args.subcommand:
        p_ang.print_help()
        sys.exit(0)
    if args.command == "events" and not args.subcommand:
        p_ev.print_help()
        sys.exit(0)
    if args.command == "msg" and not args.subcommand:
        p_msg.print_help()
        sys.exit(0)
    if args.command == "agent" and not args.subcommand:
        p_agent.print_help()
        sys.exit(0)
    
    dispatch = {
        "init": cmd_init,
        "check": cmd_check,
        "doctor": cmd_doctor,
        "config": cmd_config,
        "project": cmd_project,
        "protocol": cmd_protocol,
        "mnemosyne": cmd_mnemosyne,
        "runtime": cmd_runtime,
        "detach": cmd_detach,
        "context": cmd_context,
        "inbox": cmd_inbox,
        "angelia": cmd_angelia,
        "events": cmd_events,
        "msg": cmd_msg,
        "agent": cmd_agent,
        "test": cmd_test,
    }
    fn = dispatch.get(args.command)
    if fn is None:
        parser.print_help()
        return
    fn(args)

if __name__ == "__main__":
    main()
