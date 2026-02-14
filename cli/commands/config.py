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
            
            if parts[0] == "simulation":
                if parts[1] == "enabled":
                    data["projects"][pid]["simulation_enabled"] = args.value.lower() == "true"
                elif parts[1] == "min":
                    data["projects"][pid]["simulation_interval_min"] = int(args.value)
                elif parts[1] == "max":
                    data["projects"][pid]["simulation_interval_max"] = int(args.value)
                else:
                    print(f"❌ Unknown simulation key: {parts[1]}")
                    return
            
            elif parts[0] == "memory":
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
            
            else:
                print(f"❌ Unknown config key: {args.key}")
                print("Valid keys:")
                print("  simulation.enabled (true/false)")
                print("  simulation.min (seconds)")
                print("  simulation.max (seconds)")
                print("  memory.threshold (message count)")
                print("  memory.keep (message count)")
                print("  agent.<agent_id>.model (model name)")
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
        # List available models
        print("\n🤖 Available Models:")
        print("\n📦 Free Models:")
        print("   google/gemini-2.0-flash-exp:free")
        print("   google/gemini-flash-1.5:free")
        print("   meta-llama/llama-3.2-3b-instruct:free")
        print("   qwen/qwen-2-7b-instruct:free")
        
        print("\n💎 Premium Models:")
        print("   anthropic/claude-3.5-sonnet")
        print("   openai/gpt-4-turbo")
        print("   google/gemini-pro-1.5")
        
        print("\n💡 Usage:")
        print("   ./temple.sh config set agent.genesis.model google/gemini-2.0-flash-exp:free")
