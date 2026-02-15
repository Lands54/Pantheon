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
            print(f"\n🧱 Legacy Social API (deprecated): {data.get('enable_legacy_social_api', False)}")
            
            print(f"\n🤖 Simulation:")
            print(f"   Enabled: {proj.get('simulation_enabled', False)}")
            print(f"   Interval: {proj.get('simulation_interval_min', 10)}-{proj.get('simulation_interval_max', 40)}s")
            print(f"   Autonomous Batch Size: {proj.get('autonomous_batch_size', 4)}")
            
            print(f"\n📊 Memory:")
            print(f"   Summarize Threshold: {proj.get('summarize_threshold', 12)} messages")
            print(f"   Keep Count: {proj.get('summarize_keep_count', 5)} messages")
            print(f"   Tool Loop Max: {proj.get('tool_loop_max', 8)} per pulse")
            print(f"   Memory Compact Trigger Chars: {proj.get('memory_compact_trigger_chars', 200000)}")
            print(f"   Memory Compact Keep Chars: {proj.get('memory_compact_keep_chars', 50000)}")
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
            
            print(f"\n👥 Active Agents: {', '.join(proj.get('active_agents', []))}")
            
            print(f"\n🎛️  Agent Settings:")
            for agent_id, settings in proj.get('agent_settings', {}).items():
                print(f"   {agent_id}:")
                print(f"      Model: {settings.get('model', 'default')}")
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
            
            # Match key paths
            if parts[0] == "simulation" and len(parts) >= 2:
                if parts[1] == "enabled":
                    data["projects"][pid]["simulation_enabled"] = args.value.lower() == "true"
                elif parts[1] == "min":
                    data["projects"][pid]["simulation_interval_min"] = int(args.value)
                elif parts[1] == "max":
                    data["projects"][pid]["simulation_interval_max"] = int(args.value)
                elif parts[1] == "parallel":
                    data["projects"][pid]["autonomous_parallel"] = args.value.lower() == "true"
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
                    data["projects"][pid]["memory_compact_trigger_chars"] = int(args.value)
                elif parts[1] == "compact_keep":
                    data["projects"][pid]["memory_compact_keep_chars"] = int(args.value)
                else:
                    print(f"❌ Unknown memory key: {parts[1]}")
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

            elif parts[0] == "legacy" and len(parts) >= 2:
                if parts[1] == "social_api":
                    data["enable_legacy_social_api"] = args.value.lower() == "true"
                else:
                    print(f"❌ Unknown legacy key: {parts[1]}")
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
                print("  simulation.parallel (true/false) [deprecated/no-op]")
                print("  simulation.batch (number)")
                print("  memory.threshold (message count)")
                print("  memory.keep (message count)")
                print("  memory.compact_trigger (chars)")
                print("  memory.compact_keep (chars)")
                print("  tools.loop_max (number)")
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
                print("  legacy.social_api (true/false)")
                print("  agent.<agent_id>.model (model name)")
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
