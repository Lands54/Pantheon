"""
CLI Config Command - Configuration Management
"""
import requests
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
            print(f"\n🔑 API Key: {'SET' if data['openrouter_api_key'] else 'NOT SET'}")
            print(f"\n🌍 Current Project: {data['current_project']}")
            
            print(f"\n🤖 Simulation:")
            print(f"   Enabled: {proj.get('simulation_enabled', False)}")
            print(f"   Interval: {proj.get('simulation_interval_min', 10)}-{proj.get('simulation_interval_max', 40)}s")
            
            print(f"\n📊 Memory:")
            print(f"   Summarize Threshold: {proj.get('summarize_threshold', 12)} messages")
            print(f"   Keep Count: {proj.get('summarize_keep_count', 5)} messages")
            
            print(f"\n👥 Active Agents: {', '.join(proj.get('active_agents', []))}")
            
            print(f"\n🎛️  Agent Settings:")
            for agent_id, settings in proj.get('agent_settings', {}).items():
                print(f"   {agent_id}:")
                print(f"      Model: {settings.get('model', 'default')}")
                disabled = settings.get('disabled_tools', [])
                if disabled:
                    print(f"      Disabled Tools: {', '.join(disabled)}")
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
                else:
                    print(f"❌ Unknown simulation key: {parts[1]}")
                    return
            
            elif parts[0] == "memory" and len(parts) >= 2:
                if parts[1] == "threshold":
                    data["projects"][pid]["summarize_threshold"] = int(args.value)
                elif parts[1] == "keep":
                    data["projects"][pid]["summarize_keep_count"] = int(args.value)
                else:
                    print(f"❌ Unknown memory key: {parts[1]}")
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
                print("  memory.threshold (message count)")
                print("  memory.keep (message count)")
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
            # Get API key if available
            res = requests.get(f"{base_url}/config")
            api_key = res.json().get("openrouter_api_key", "")
            
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
