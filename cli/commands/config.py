"""
CLI Config Command - Configuration Management
"""
import requests
import json
from pathlib import Path
from cli.utils import get_base_url, handle_response


def cmd_config(args):
    """Manage system and agent configurations."""
    base_url = get_base_url()
    
    if args.subcommand == "show":
        # Show current configuration
        try:
            res = requests.get(f"{base_url}/config")
            data = res.json()
            pid = args.project or data.get("current_project", "default")
            proj = data["projects"].get(pid)
            
            if not proj:
                print(f"❌ Project '{pid}' not found.")
                return
            
            print(f"\n⚙️  CONFIGURATION - Project: {pid}")
            print(f"\n🔑 API Key: {'SET' if data.get('has_openrouter_api_key') else 'NOT SET'}")
            print(f"\n🌍 Current Project: {data['current_project']}")
            
            print(f"\n🤖 Simulation:")
            print(f"   Enabled: {proj.get('simulation_enabled', False)}")
            print(f"   Interval: {proj.get('simulation_interval_min', 10)}-{proj.get('simulation_interval_max', 40)}s")
            print(f"   Autonomous Batch Size: {proj.get('autonomous_batch_size', 4)}")
            print(f"   Queue Idle Heartbeat: {proj.get('queue_idle_heartbeat_sec', 60)}s")
            print(f"   Event Inject Budget: {proj.get('pulse_event_inject_budget', 3)}")
            print(f"   Interrupt Mode: {proj.get('pulse_interrupt_mode', 'after_action')}")
            print(f"   Inbox Event Enabled: {proj.get('inbox_event_enabled', True)}")
            print(f"   Angelia Enabled: {proj.get('angelia_enabled', True)}")
            print(f"   Angelia Timer Enabled: {proj.get('angelia_timer_enabled', True)}")
            print(f"   Angelia Timer Idle: {proj.get('angelia_timer_idle_sec', 60)}s")
            print(f"   Angelia Max Attempts: {proj.get('angelia_event_max_attempts', 3)}")
            print(f"   Angelia Processing Timeout: {proj.get('angelia_processing_timeout_sec', 60)}s")
            print(f"   Angelia Cooldown Preempt Types: {proj.get('angelia_cooldown_preempt_types', ['inbox_event','manual'])}")
            print(f"   Angelia Dedupe Window: {proj.get('angelia_dedupe_window_sec', 5)}s")
            
            print(f"\n📊 Memory:")
            print(f"   Summarize Threshold: {proj.get('summarize_threshold', 12)} messages")
            print(f"   Keep Count: {proj.get('summarize_keep_count', 5)} messages")
            print(f"   Tool Loop Max: {proj.get('tool_loop_max', 8)} per pulse")
            print(f"   Memory Compact Trigger Tokens: {proj.get('memory_compact_trigger_tokens', 12000)}")
            print(f"   Memory Compact Strategy: {proj.get('memory_compact_strategy', 'semantic_llm')}")
            print(f"\n🪞 Janus Context:")
            print(f"   Strategy: {proj.get('context_strategy', 'structured_v1')}")
            print(f"   Token Budget Total: {proj.get('context_token_budget_total', 32000)}")
            print(f"   Budget Task State: {proj.get('context_budget_task_state', 4000)}")
            print(f"   Budget Observations: {proj.get('context_budget_observations', 12000)}")
            print(f"   Budget Inbox: {proj.get('context_budget_inbox', 4000)}")
            print(f"   Budget State Window: {proj.get('context_budget_state_window', 12000)}")
            print(f"   State Window Limit: {proj.get('context_state_window_limit', 50)}")
            print(f"   Observation Window: {proj.get('context_observation_window', 30)}")
            print(f"   Include Inbox Status Hints: {proj.get('context_include_inbox_status_hints', True)}")
            print(f"   Write Build Report: {proj.get('context_write_build_report', True)}")
            print(f"\n🧠 Phase Runtime:")
            print(f"   Enabled: {proj.get('phase_mode_enabled', True)}")
            print(f"   Strategy: {proj.get('phase_strategy', 'strict_triad')}")
            print(f"   Interaction Max: {proj.get('phase_interaction_max', 3)}")
            print(f"   Act Require Tool Call: {proj.get('phase_act_require_tool_call', True)}")
            print(f"   Act Require Productive Tool: {proj.get('phase_act_require_productive_tool', True)}")
            print(f"   Act Productive From Interaction: {proj.get('phase_act_productive_from_interaction', 2)}")
            print(f"   Repeat Limit: {proj.get('phase_repeat_limit', 2)}")
            print(f"   Explore Budget: {proj.get('phase_explore_budget', 3)}")
            print(f"   No Progress Limit: {proj.get('phase_no_progress_limit', 3)}")
            print(f"   Single Tool Call: {proj.get('phase_single_tool_call', True)}")
            print(f"\n🪵 Debug Trace:")
            print(f"   Enabled: {proj.get('debug_trace_enabled', True)}")
            print(f"   Max Events Per Pulse: {proj.get('debug_trace_max_events', 200)}")
            print(f"   Full Content: {proj.get('debug_trace_full_content', True)}")
            print(f"   LLM IO Trace Enabled: {proj.get('debug_llm_trace_enabled', True)}")
            print(f"\n📡 Hermes Bus:")
            print(f"   Enabled: {proj.get('hermes_enabled', True)}")
            print(f"   Default Timeout: {proj.get('hermes_default_timeout_sec', 30)}s")
            print(f"   Default Rate Limit: {proj.get('hermes_default_rate_per_minute', 60)} /min")
            print(f"   Default Max Concurrency: {proj.get('hermes_default_max_concurrency', 2)}")
            print(f"   Allow agent_tool Provider: {proj.get('hermes_allow_agent_tool_provider', False)}")
            print(f"\n🐳 Runtime (Command Executor):")
            print(f"   Executor: {proj.get('command_executor', 'local')}")
            print(f"   Docker Enabled: {proj.get('docker_enabled', True)}")
            print(f"   Docker Image: {proj.get('docker_image', 'gods-agent-base:py311')}")
            print(f"   Docker Network Mode: {proj.get('docker_network_mode', 'bridge_local_only')}")
            print(f"   Docker Auto Start on Project Start: {proj.get('docker_auto_start_on_project_start', True)}")
            print(f"   Docker Auto Stop on Project Stop: {proj.get('docker_auto_stop_on_project_stop', True)}")
            print(f"   Docker Workspace Mount Mode: {proj.get('docker_workspace_mount_mode', 'agent_territory_rw')}")
            print(f"   Docker Readonly Rootfs: {proj.get('docker_readonly_rootfs', False)}")
            print(f"   Docker CPU Limit: {proj.get('docker_cpu_limit', 1.0)}")
            print(f"   Docker Memory Limit: {proj.get('docker_memory_limit_mb', 512)} MB")
            print(f"   Docker Extra Env: {proj.get('docker_extra_env', {})}")
            print(f"\n🧵 Detach Runtime:")
            print(f"   Enabled: {proj.get('detach_enabled', True)}")
            print(f"   Max Running Per Agent: {proj.get('detach_max_running_per_agent', 2)}")
            print(f"   Max Running Per Project: {proj.get('detach_max_running_per_project', 8)}")
            print(f"   Queue Max Per Agent: {proj.get('detach_queue_max_per_agent', 8)}")
            print(f"   TTL: {proj.get('detach_ttl_sec', 1800)}s")
            print(f"   Stop Grace: {proj.get('detach_stop_grace_sec', 10)}s")
            print(f"   Log Tail Chars: {proj.get('detach_log_tail_chars', 4000)}")
            
            print(f"\n👥 Active Agents: {', '.join(proj.get('active_agents', []))}")
            
            print(f"\n🎛️  Agent Settings:")
            for agent_id, settings in proj.get('agent_settings', {}).items():
                print(f"   {agent_id}:")
                print(f"      Model: {settings.get('model', 'default')}")
                if settings.get("phase_strategy") is not None:
                    print(f"      Phase Strategy Override: {settings.get('phase_strategy')}")
                if settings.get("phase_mode_enabled") is not None:
                    print(f"      Phase Enabled Override: {settings.get('phase_mode_enabled')}")
                if settings.get("context_strategy") is not None:
                    print(f"      Context Strategy Override: {settings.get('context_strategy')}")
                if settings.get("context_token_budget_total") is not None:
                    print(f"      Context Token Budget Override: {settings.get('context_token_budget_total')}")
                disabled = settings.get('disabled_tools', [])
                if disabled:
                    print(f"      Disabled Tools: {', '.join(disabled)}")

            # Show scheduler runtime status
            try:
                s_res = requests.get(f"{base_url}/agents/status", params={"project_id": pid}, timeout=3)
                s_data = s_res.json()
                agents = s_data.get("agents", [])
                if agents:
                    from datetime import datetime
                    print(f"\n🧭 Scheduler Status:")
                    for item in agents:
                        status = item.get("status", "unknown")
                        lp = item.get("last_pulse_at", 0) or 0
                        ne = item.get("next_eligible_at", 0) or 0
                        lp_s = datetime.fromtimestamp(lp).strftime("%Y-%m-%d %H:%M:%S") if lp > 0 else "N/A"
                        ne_s = datetime.fromtimestamp(ne).strftime("%Y-%m-%d %H:%M:%S") if ne > 0 else "N/A"
                        print(f"   {item.get('agent_id')}: {status}")
                        print(f"      Last Pulse: {lp_s}")
                        print(f"      Next Eligible: {ne_s}")
                        print(f"      Empty Cycles: {item.get('empty_cycles', 0)}")
                        print(f"      Pending Inbox: {item.get('has_pending_inbox', False)}")
                else:
                    print(f"\n🧭 Scheduler Status: No active agents in this project")
            except Exception as e:
                print(f"\n🧭 Scheduler Status: unavailable ({e})")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    elif args.subcommand == "set":
        # Set configuration value
        try:
            res = requests.get(f"{base_url}/config")
            data = res.json()
            pid = args.project or data.get("current_project", "default")
            
            if pid not in data["projects"]:
                print(f"❌ Project '{pid}' not found.")
                return
            
            # Parse key path (e.g., "simulation.enabled" or "agent.genesis.model")
            parts = args.key.split('.')
            direct_key = args.key.strip()

            if direct_key in {
                "queue_idle_heartbeat_sec",
                "pulse_event_inject_budget",
                "pulse_interrupt_mode",
                "inbox_event_enabled",
                "pulse_priority_weights",
                "angelia_enabled",
                "angelia_worker_per_agent",
                "angelia_event_max_attempts",
                "angelia_processing_timeout_sec",
                "angelia_cooldown_preempt_types",
                "angelia_timer_enabled",
                "angelia_timer_idle_sec",
                "angelia_dedupe_window_sec",
                "command_executor",
                "docker_enabled",
                "docker_image",
                "docker_network_mode",
                "docker_auto_start_on_project_start",
                "docker_auto_stop_on_project_stop",
                "docker_workspace_mount_mode",
                "docker_readonly_rootfs",
                "docker_extra_env",
                "docker_cpu_limit",
                "docker_memory_limit_mb",
                "detach_enabled",
                "detach_max_running_per_agent",
                "detach_max_running_per_project",
                "detach_queue_max_per_agent",
                "detach_ttl_sec",
                "detach_stop_grace_sec",
                "detach_log_tail_chars",
                "context_strategy",
                "context_token_budget_total",
                "context_budget_task_state",
                "context_budget_observations",
                "context_budget_inbox",
                "context_budget_state_window",
                "context_state_window_limit",
                "context_observation_window",
                "context_include_inbox_status_hints",
                "context_write_build_report",
            }:
                if direct_key in {
                    "queue_idle_heartbeat_sec",
                    "pulse_event_inject_budget",
                    "angelia_worker_per_agent",
                    "angelia_event_max_attempts",
                    "angelia_processing_timeout_sec",
                    "angelia_timer_idle_sec",
                    "angelia_dedupe_window_sec",
                }:
                    data["projects"][pid][direct_key] = int(args.value)
                elif direct_key in {"docker_memory_limit_mb"}:
                    data["projects"][pid][direct_key] = int(args.value)
                elif direct_key in {
                    "detach_max_running_per_agent",
                    "detach_max_running_per_project",
                    "detach_queue_max_per_agent",
                    "detach_ttl_sec",
                    "detach_stop_grace_sec",
                    "detach_log_tail_chars",
                    "context_token_budget_total",
                    "context_budget_task_state",
                    "context_budget_observations",
                    "context_budget_inbox",
                    "context_budget_state_window",
                    "context_state_window_limit",
                "context_observation_window",
                }:
                    data["projects"][pid][direct_key] = int(args.value)
                elif direct_key in {"docker_cpu_limit"}:
                    data["projects"][pid][direct_key] = float(args.value)
                elif direct_key in {"inbox_event_enabled", "angelia_enabled", "angelia_timer_enabled"}:
                    data["projects"][pid][direct_key] = args.value.lower() == "true"
                elif direct_key in {
                    "docker_enabled",
                    "docker_auto_start_on_project_start",
                    "docker_auto_stop_on_project_stop",
                    "docker_readonly_rootfs",
                    "detach_enabled",
                    "context_include_inbox_status_hints",
                    "context_write_build_report",
                }:
                    data["projects"][pid][direct_key] = args.value.lower() == "true"
                elif direct_key == "context_strategy":
                    if args.value not in {"structured_v1"}:
                        print("❌ context_strategy must be: structured_v1")
                        return
                    data["projects"][pid][direct_key] = args.value
                elif direct_key == "command_executor":
                    if args.value not in {"docker", "local"}:
                        print("❌ command_executor must be one of: docker, local")
                        return
                    data["projects"][pid][direct_key] = args.value
                elif direct_key == "docker_extra_env":
                    try:
                        payload = json.loads(args.value)
                        if not isinstance(payload, dict):
                            print("❌ docker_extra_env must be a JSON object")
                            return
                        data["projects"][pid][direct_key] = payload
                    except Exception as e:
                        print(f"❌ invalid JSON for docker_extra_env: {e}")
                        return
                elif direct_key == "pulse_interrupt_mode":
                    if args.value != "after_action":
                        print("❌ pulse_interrupt_mode currently only supports: after_action")
                        return
                    data["projects"][pid][direct_key] = args.value
                elif direct_key == "pulse_priority_weights":
                    try:
                        payload = json.loads(args.value)
                        if not isinstance(payload, dict):
                            print("❌ pulse_priority_weights must be a JSON object")
                            return
                        data["projects"][pid][direct_key] = payload
                    except Exception as e:
                        print(f"❌ invalid JSON for pulse_priority_weights: {e}")
                        return
                elif direct_key == "angelia_cooldown_preempt_types":
                    try:
                        payload = json.loads(args.value)
                        if not isinstance(payload, list):
                            print("❌ angelia_cooldown_preempt_types must be a JSON array")
                            return
                        data["projects"][pid][direct_key] = [str(x).strip() for x in payload if str(x).strip()]
                    except Exception as e:
                        print(f"❌ invalid JSON for angelia_cooldown_preempt_types: {e}")
                        return
                else:
                    data["projects"][pid][direct_key] = args.value

            # Match key paths
            elif parts[0] == "simulation" and len(parts) >= 2:
                if parts[1] == "enabled":
                    data["projects"][pid]["simulation_enabled"] = args.value.lower() == "true"
                elif parts[1] == "min":
                    data["projects"][pid]["simulation_interval_min"] = int(args.value)
                elif parts[1] == "max":
                    data["projects"][pid]["simulation_interval_max"] = int(args.value)
                elif parts[1] == "batch":
                    data["projects"][pid]["autonomous_batch_size"] = int(args.value)
                else:
                    print(f"❌ Unknown simulation key: {parts[1]}")
                    return
            
            elif parts[0] == "memory" and len(parts) >= 2:
                if parts[1] == "threshold":
                    data["projects"][pid]["summarize_threshold"] = int(args.value)
                elif parts[1] == "keep":
                    data["projects"][pid]["summarize_keep_count"] = int(args.value)
                elif parts[1] == "compact_trigger":
                    data["projects"][pid]["memory_compact_trigger_tokens"] = int(args.value)
                elif parts[1] == "compact_strategy":
                    value = str(args.value).strip().lower()
                    if value not in {"semantic_llm", "rule_based"}:
                        print("❌ memory.compact_strategy must be semantic_llm | rule_based")
                        return
                    data["projects"][pid]["memory_compact_strategy"] = value
                else:
                    print(f"❌ Unknown memory key: {parts[1]}")
                    return
            elif parts[0] == "context" and len(parts) >= 2:
                if parts[1] == "strategy":
                    if args.value not in {"structured_v1"}:
                        print("❌ context.strategy must be: structured_v1")
                        return
                    data["projects"][pid]["context_strategy"] = args.value
                elif parts[1] == "token_budget_total":
                    data["projects"][pid]["context_token_budget_total"] = int(args.value)
                elif parts[1] == "state_window_limit":
                    data["projects"][pid]["context_state_window_limit"] = int(args.value)
                elif parts[1] == "observation_window":
                    data["projects"][pid]["context_observation_window"] = int(args.value)
                elif parts[1] == "include_inbox_status_hints":
                    data["projects"][pid]["context_include_inbox_status_hints"] = args.value.lower() == "true"
                elif parts[1] == "write_build_report":
                    data["projects"][pid]["context_write_build_report"] = args.value.lower() == "true"
                elif parts[1] == "budget" and len(parts) >= 3:
                    if parts[2] == "task_state":
                        data["projects"][pid]["context_budget_task_state"] = int(args.value)
                    elif parts[2] == "observations":
                        data["projects"][pid]["context_budget_observations"] = int(args.value)
                    elif parts[2] == "inbox":
                        data["projects"][pid]["context_budget_inbox"] = int(args.value)
                    elif parts[2] == "state_window":
                        data["projects"][pid]["context_budget_state_window"] = int(args.value)
                    else:
                        print(f"❌ Unknown context budget key: {parts[2]}")
                        return
                else:
                    print(f"❌ Unknown context key: {parts[1]}")
                    return

            elif parts[0] == "tools" and len(parts) >= 2:
                if parts[1] == "loop_max":
                    value = int(args.value)
                    if value < 1:
                        print("❌ tools.loop_max must be >= 1")
                        return
                    data["projects"][pid]["tool_loop_max"] = value
                else:
                    print(f"❌ Unknown tools key: {parts[1]}")
                    return

            elif parts[0] == "phase" and len(parts) >= 2:
                if parts[1] == "enabled":
                    data["projects"][pid]["phase_mode_enabled"] = args.value.lower() == "true"
                elif parts[1] == "strategy":
                    if args.value not in ("strict_triad", "iterative_action", "freeform"):
                        print("❌ phase.strategy must be one of: strict_triad, iterative_action, freeform")
                        return
                    data["projects"][pid]["phase_strategy"] = args.value
                elif parts[1] == "interaction_max":
                    value = int(args.value)
                    if value < 1:
                        print("❌ phase.interaction_max must be >= 1")
                        return
                    data["projects"][pid]["phase_interaction_max"] = value
                elif parts[1] == "act_require_tool":
                    data["projects"][pid]["phase_act_require_tool_call"] = args.value.lower() == "true"
                elif parts[1] == "act_require_productive":
                    data["projects"][pid]["phase_act_require_productive_tool"] = args.value.lower() == "true"
                elif parts[1] == "act_productive_from":
                    value = int(args.value)
                    if value < 1:
                        print("❌ phase.act_productive_from must be >= 1")
                        return
                    data["projects"][pid]["phase_act_productive_from_interaction"] = value
                elif parts[1] == "repeat_limit":
                    data["projects"][pid]["phase_repeat_limit"] = int(args.value)
                elif parts[1] == "explore_budget":
                    data["projects"][pid]["phase_explore_budget"] = int(args.value)
                elif parts[1] == "no_progress_limit":
                    data["projects"][pid]["phase_no_progress_limit"] = int(args.value)
                elif parts[1] == "single_tool":
                    data["projects"][pid]["phase_single_tool_call"] = args.value.lower() == "true"
                else:
                    print(f"❌ Unknown phase key: {parts[1]}")
                    return
            elif parts[0] == "pulse" and len(parts) >= 2:
                if parts[1] == "idle_heartbeat":
                    data["projects"][pid]["queue_idle_heartbeat_sec"] = int(args.value)
                elif parts[1] == "inject_budget":
                    data["projects"][pid]["pulse_event_inject_budget"] = int(args.value)
                elif parts[1] == "interrupt_mode":
                    if args.value != "after_action":
                        print("❌ pulse.interrupt_mode currently only supports: after_action")
                        return
                    data["projects"][pid]["pulse_interrupt_mode"] = args.value
                elif parts[1] == "inbox_event":
                    data["projects"][pid]["inbox_event_enabled"] = args.value.lower() == "true"
                elif parts[1] == "weights":
                    try:
                        payload = json.loads(args.value)
                    except Exception as e:
                        print(f"❌ invalid JSON for pulse.weights: {e}")
                        return
                    if not isinstance(payload, dict):
                        print("❌ pulse.weights must be a JSON object")
                        return
                    data["projects"][pid]["pulse_priority_weights"] = payload
                else:
                    print(f"❌ Unknown pulse key: {parts[1]}")
                    return
            elif parts[0] == "debug" and len(parts) >= 2:
                if parts[1] == "trace":
                    data["projects"][pid]["debug_trace_enabled"] = args.value.lower() == "true"
                elif parts[1] == "max_events":
                    value = int(args.value)
                    if value < 20:
                        print("❌ debug.max_events must be >= 20")
                        return
                    data["projects"][pid]["debug_trace_max_events"] = value
                elif parts[1] == "full":
                    data["projects"][pid]["debug_trace_full_content"] = args.value.lower() == "true"
                elif parts[1] == "llm_trace":
                    data["projects"][pid]["debug_llm_trace_enabled"] = args.value.lower() == "true"
                else:
                    print(f"❌ Unknown debug key: {parts[1]}")
                    return
            elif parts[0] == "hermes" and len(parts) >= 2:
                if parts[1] == "enabled":
                    data["projects"][pid]["hermes_enabled"] = args.value.lower() == "true"
                elif parts[1] == "timeout":
                    data["projects"][pid]["hermes_default_timeout_sec"] = int(args.value)
                elif parts[1] == "rate":
                    data["projects"][pid]["hermes_default_rate_per_minute"] = int(args.value)
                elif parts[1] == "concurrency":
                    data["projects"][pid]["hermes_default_max_concurrency"] = int(args.value)
                elif parts[1] == "allow_agent_tool":
                    data["projects"][pid]["hermes_allow_agent_tool_provider"] = args.value.lower() == "true"
                else:
                    print(f"❌ Unknown hermes key: {parts[1]}")
                    return
            elif parts[0] == "docker" and len(parts) >= 2:
                if parts[1] == "enabled":
                    data["projects"][pid]["docker_enabled"] = args.value.lower() == "true"
                elif parts[1] == "image":
                    data["projects"][pid]["docker_image"] = args.value
                elif parts[1] == "network_mode":
                    data["projects"][pid]["docker_network_mode"] = args.value
                elif parts[1] == "auto_start":
                    data["projects"][pid]["docker_auto_start_on_project_start"] = args.value.lower() == "true"
                elif parts[1] == "auto_stop":
                    data["projects"][pid]["docker_auto_stop_on_project_stop"] = args.value.lower() == "true"
                elif parts[1] == "readonly_rootfs":
                    data["projects"][pid]["docker_readonly_rootfs"] = args.value.lower() == "true"
                elif parts[1] == "cpu":
                    data["projects"][pid]["docker_cpu_limit"] = float(args.value)
                elif parts[1] == "memory_mb":
                    data["projects"][pid]["docker_memory_limit_mb"] = int(args.value)
                elif parts[1] == "extra_env":
                    try:
                        payload = json.loads(args.value)
                    except Exception as e:
                        print(f"❌ invalid JSON for docker.extra_env: {e}")
                        return
                    if not isinstance(payload, dict):
                        print("❌ docker.extra_env must be a JSON object")
                        return
                    data["projects"][pid]["docker_extra_env"] = payload
                else:
                    print(f"❌ Unknown docker key: {parts[1]}")
                    return
            elif parts[0] == "detach" and len(parts) >= 2:
                if parts[1] == "enabled":
                    data["projects"][pid]["detach_enabled"] = args.value.lower() == "true"
                elif parts[1] == "max_running_per_agent":
                    data["projects"][pid]["detach_max_running_per_agent"] = int(args.value)
                elif parts[1] == "max_running_per_project":
                    data["projects"][pid]["detach_max_running_per_project"] = int(args.value)
                elif parts[1] == "queue_max_per_agent":
                    data["projects"][pid]["detach_queue_max_per_agent"] = int(args.value)
                elif parts[1] == "ttl":
                    data["projects"][pid]["detach_ttl_sec"] = int(args.value)
                elif parts[1] == "stop_grace":
                    data["projects"][pid]["detach_stop_grace_sec"] = int(args.value)
                elif parts[1] == "log_tail_chars":
                    data["projects"][pid]["detach_log_tail_chars"] = int(args.value)
                else:
                    print(f"❌ Unknown detach key: {parts[1]}")
                    return
            elif parts[0] == "executor" and len(parts) >= 2:
                if parts[1] == "command":
                    if args.value not in {"docker", "local"}:
                        print("❌ executor.command must be one of: docker, local")
                        return
                    data["projects"][pid]["command_executor"] = args.value
                else:
                    print(f"❌ Unknown executor key: {parts[1]}")
                    return

            elif parts[0] == "agent" and len(parts) >= 3:
                agent_id = parts[1]
                setting = parts[2]
                
                if "agent_settings" not in data["projects"][pid]:
                    data["projects"][pid]["agent_settings"] = {}
                if agent_id not in data["projects"][pid]["agent_settings"]:
                    data["projects"][pid]["agent_settings"][agent_id] = {}
                
                if setting == "model":
                    data["projects"][pid]["agent_settings"][agent_id]["model"] = args.value
                elif setting == "phase_strategy":
                    if args.value not in ("strict_triad", "iterative_action", "freeform"):
                        print("❌ agent.<id>.phase_strategy must be one of: strict_triad, iterative_action, freeform")
                        return
                    data["projects"][pid]["agent_settings"][agent_id]["phase_strategy"] = args.value
                elif setting == "phase_enabled":
                    data["projects"][pid]["agent_settings"][agent_id]["phase_mode_enabled"] = args.value.lower() == "true"
                elif setting == "context_strategy":
                    if args.value not in ("structured_v1",):
                        print("❌ agent.<id>.context_strategy must be: structured_v1")
                        return
                    data["projects"][pid]["agent_settings"][agent_id]["context_strategy"] = args.value
                elif setting == "context_token_budget_total":
                    data["projects"][pid]["agent_settings"][agent_id]["context_token_budget_total"] = int(args.value)
                elif setting == "disabled_tools":
                    raw = str(args.value or "").strip()
                    if raw.lower() in {"", "none", "null", "[]"}:
                        tools = []
                    else:
                        tools = [x.strip() for x in raw.split(",") if x.strip()]
                    # keep insertion order while removing duplicates
                    seen = set()
                    normalized = []
                    for t in tools:
                        if t in seen:
                            continue
                        seen.add(t)
                        normalized.append(t)
                    data["projects"][pid]["agent_settings"][agent_id]["disabled_tools"] = normalized
                elif setting == "disable_tool":
                    tool_name = str(args.value or "").strip()
                    if not tool_name:
                        print("❌ agent.<id>.disable_tool requires a tool name")
                        return
                    current = data["projects"][pid]["agent_settings"][agent_id].get("disabled_tools", [])
                    if not isinstance(current, list):
                        current = []
                    if tool_name not in current:
                        current.append(tool_name)
                    data["projects"][pid]["agent_settings"][agent_id]["disabled_tools"] = current
                elif setting == "enable_tool":
                    tool_name = str(args.value or "").strip()
                    if not tool_name:
                        print("❌ agent.<id>.enable_tool requires a tool name")
                        return
                    current = data["projects"][pid]["agent_settings"][agent_id].get("disabled_tools", [])
                    if not isinstance(current, list):
                        current = []
                    data["projects"][pid]["agent_settings"][agent_id]["disabled_tools"] = [t for t in current if t != tool_name]
                else:
                    print(f"❌ Unknown agent setting: {setting}")
                    return
            
            # BATCH SETTING: Set model for ALL agents in the current project
            elif parts[0] == "all" and parts[1] == "models":
                if "agent_settings" not in data["projects"][pid]:
                    data["projects"][pid]["agent_settings"] = {}
                
                # Get all active agents and existing settings
                agents_to_update = set(data["projects"][pid].get("active_agents", []))
                agents_to_update.update(data["projects"][pid]["agent_settings"].keys())
                
                if not agents_to_update:
                    # Fallback to default
                    agents_to_update = {"genesis"}
                
                for agent_id in agents_to_update:
                    if agent_id not in data["projects"][pid]["agent_settings"]:
                        data["projects"][pid]["agent_settings"][agent_id] = {}
                    data["projects"][pid]["agent_settings"][agent_id]["model"] = args.value
                
                print(f"🚀 Updating all agents to model: {args.value}")
            
            else:
                print(f"❌ Unknown config key: {args.key}")
                print("Valid keys:")
                print("  simulation.enabled (true/false)")
                print("  simulation.min (seconds)")
                print("  simulation.max (seconds)")
                print("  simulation.batch (number)")
                print("  queue_idle_heartbeat_sec (seconds)")
                print("  pulse_event_inject_budget (number)")
                print("  pulse_interrupt_mode (after_action)")
                print("  inbox_event_enabled (true/false)")
                print("  pulse_priority_weights ({\"inbox_event\":100,...})")
                print("  memory.threshold (message count)")
                print("  memory.keep (message count)")
                print("  memory.compact_trigger (tokens)")
                print("  memory.compact_strategy (semantic_llm|rule_based)")
                print("  context.strategy (structured_v1)")
                print("  context.token_budget_total (tokens)")
                print("  context.budget.task_state (tokens)")
                print("  context.budget.observations (tokens)")
                print("  context.budget.inbox (tokens)")
                print("  context.budget.state_window (tokens)")
                print("  context.state_window_limit (count)")
                print("  context.observation_window (count)")
                print("  context.include_inbox_status_hints (true/false)")
                print("  context.write_build_report (true/false)")
                print("  tools.loop_max (number)")
                print("  pulse.idle_heartbeat (seconds)")
                print("  pulse.inject_budget (number)")
                print("  pulse.interrupt_mode (after_action)")
                print("  pulse.inbox_event (true/false)")
                print("  pulse.weights ({\"inbox_event\":100,...})")
                print("  phase.enabled (true/false)")
                print("  phase.strategy (strict_triad|iterative_action|freeform)")
                print("  phase.interaction_max (number)")
                print("  phase.act_require_tool (true/false)")
                print("  phase.act_require_productive (true/false)")
                print("  phase.act_productive_from (number)")
                print("  phase.repeat_limit (number)")
                print("  phase.explore_budget (number)")
                print("  phase.no_progress_limit (number)")
                print("  phase.single_tool (true/false)")
                print("  debug.trace (true/false)")
                print("  debug.max_events (number)")
                print("  debug.full (true/false)")
                print("  debug.llm_trace (true/false)")
                print("  hermes.enabled (true/false)")
                print("  hermes.timeout (seconds)")
                print("  hermes.rate (calls/min)")
                print("  hermes.concurrency (number)")
                print("  hermes.allow_agent_tool (true/false)")
                print("  command_executor (docker|local)")
                print("  docker_enabled (true/false)")
                print("  docker_image (image tag)")
                print("  docker_network_mode (bridge_local_only|none)")
                print("  docker_auto_start_on_project_start (true/false)")
                print("  docker_auto_stop_on_project_stop (true/false)")
                print("  docker_workspace_mount_mode (agent_territory_rw)")
                print("  docker_readonly_rootfs (true/false)")
                print("  docker_cpu_limit (float)")
                print("  docker_memory_limit_mb (int)")
                print("  docker_extra_env ({\"KEY\":\"VALUE\"})")
                print("  detach_enabled (true/false)")
                print("  detach_max_running_per_agent (int)")
                print("  detach_max_running_per_project (int)")
                print("  detach_queue_max_per_agent (int)")
                print("  detach_ttl_sec (seconds)")
                print("  detach_stop_grace_sec (seconds)")
                print("  detach_log_tail_chars (int)")
                print("  context_strategy (structured_v1)")
                print("  context_token_budget_total (tokens)")
                print("  context_budget_task_state (tokens)")
                print("  context_budget_observations (tokens)")
                print("  context_budget_inbox (tokens)")
                print("  context_budget_state_window (tokens)")
                print("  context_state_window_limit (count)")
                print("  context_observation_window (count)")
                print("  context_include_inbox_status_hints (true/false)")
                print("  context_write_build_report (true/false)")
                print("  executor.command (docker|local)")
                print("  docker.enabled (true/false)")
                print("  docker.image (image tag)")
                print("  docker.network_mode (bridge_local_only|none)")
                print("  docker.auto_start (true/false)")
                print("  docker.auto_stop (true/false)")
                print("  docker.readonly_rootfs (true/false)")
                print("  docker.cpu (float)")
                print("  docker.memory_mb (int)")
                print("  docker.extra_env ({\"KEY\":\"VALUE\"})")
                print("  detach.enabled (true/false)")
                print("  detach.max_running_per_agent (int)")
                print("  detach.max_running_per_project (int)")
                print("  detach.queue_max_per_agent (int)")
                print("  detach.ttl (seconds)")
                print("  detach.stop_grace (seconds)")
                print("  detach.log_tail_chars (int)")
                print("  agent.<agent_id>.model (model name)")
                print("  agent.<agent_id>.context_strategy (structured_v1)")
                print("  agent.<agent_id>.context_token_budget_total (tokens)")
                print("  agent.<agent_id>.phase_strategy (strict_triad|iterative_action|freeform)")
                print("  agent.<agent_id>.phase_enabled (true/false)")
                print("  agent.<agent_id>.disabled_tools (comma-separated, e.g. check_inbox,send_message)")
                print("  agent.<agent_id>.disable_tool (single tool name, append)")
                print("  agent.<agent_id>.enable_tool (single tool name, remove)")
                print("  all.models (model name) - SETS FOR ALL AGENTS")
                return
            
            # Save configuration
            res = requests.post(f"{base_url}/config/save", json=data)
            if res.status_code == 200:
                print(f"✅ Configuration updated: {args.key} = {args.value}")
            else:
                print(f"❌ Failed to save configuration")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    elif args.subcommand == "check-memory-policy":
        try:
            res = requests.get(f"{base_url}/config")
            data = res.json()
            pid = (args.project or data.get("current_project", "default")).strip()
            from gods.mnemosyne import validate_memory_policy

            out = validate_memory_policy(pid, ensure_exists=True)
            print(f"✅ memory policy valid for project={pid}")
            print(f"   required_keys: {out.get('required_keys', 0)}")
            print(f"   validated_keys: {out.get('validated_keys', 0)}")
        except Exception as e:
            print(f"❌ memory policy invalid: {e}")
            raise SystemExit(1)

    elif args.subcommand == "models":
        # Fetch available models from OpenRouter API
        print("\n🤖 Fetching Available Models from OpenRouter...")
        try:
            # Read local config.json for API key because server endpoint is redacted.
            api_key = ""
            cfg_path = Path("config.json")
            if cfg_path.exists():
                try:
                    payload = json.loads(cfg_path.read_text(encoding="utf-8"))
                    api_key = str(payload.get("openrouter_api_key", "") or "")
                except Exception:
                    api_key = ""
            
            # Fetch models from OpenRouter
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            models_res = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
                timeout=5
            )
            
            if models_res.status_code == 200:
                models_data = models_res.json()
                models = models_data.get("data", [])
                
                # Separate free and paid models
                free_models = []
                paid_models = []
                
                for model in models:
                    model_id = model.get("id", "")
                    pricing = model.get("pricing", {})
                    prompt_price = float(pricing.get("prompt", "0"))
                    
                    # Check if it's free (some models have :free suffix or zero pricing)
                    if ":free" in model_id or prompt_price == 0:
                        free_models.append({
                            "id": model_id,
                            "name": model.get("name", model_id),
                            "context": model.get("context_length", "unknown")
                        })
                    else:
                        paid_models.append({
                            "id": model_id,
                            "name": model.get("name", model_id),
                            "context": model.get("context_length", "unknown"),
                            "price": prompt_price
                        })
                
                # Display free models
                print("\n📦 Free Models:")
                if free_models:
                    for model in sorted(free_models, key=lambda x: x["name"])[:10]:  # Show top 10
                        print(f"   {model['id']}")
                        print(f"      Name: {model['name']}")
                        print(f"      Context: {model['context']} tokens")
                else:
                    print("   No free models found")
                
                # Display some popular paid models
                print("\n💎 Popular Premium Models:")
                popular_keywords = ["claude", "gpt-4", "gemini-pro"]
                shown = 0
                for model in sorted(paid_models, key=lambda x: x.get("price", 999)):
                    if shown >= 10:
                        break
                    if any(kw in model["id"].lower() for kw in popular_keywords):
                        print(f"   {model['id']}")
                        print(f"      Name: {model['name']}")
                        print(f"      Context: {model['context']} tokens")
                        shown += 1
                
                print(f"\n📊 Total: {len(free_models)} free, {len(paid_models)} premium models")
                print(f"💡 Full list: https://openrouter.ai/models")
            else:
                raise Exception("API request failed")
                
        except Exception as e:
            # Fallback to hardcoded list
            print(f"\n⚠️  Could not fetch from OpenRouter API: {e}")
            print("\n📦 Common Free Models:")
            print("   stepfun/step-3.5-flash:free")
            print("   stepfun/step-3.5-flash:free")
            print("   meta-llama/llama-3.2-3b-instruct:free")
            print("   qwen/qwen-2-7b-instruct:free")
            
            print("\n💎 Popular Premium Models:")
            print("   anthropic/claude-3.5-sonnet")
            print("   openai/gpt-4-turbo")
            print("   google/gemini-pro-1.5")
        
        print("\n💡 Usage:")
        print("   ./temple.sh config set agent.genesis.model stepfun/step-3.5-flash:free")
