"""
Test Script: Divine Manifestation
Demonstrates an Agent using its Divine Tools to create a specific file within a project.
"""
import sys
import os
import argparse
from pathlib import Path

# Ensure we can import from the current directory
sys.path.append(os.getcwd())

from platform_logic.agents import GodAgent
from gods_platform.graph_state import GodsState
from langchain_core.messages import HumanMessage
from gods_platform.config import runtime_config

def run_test(agent_id: str, project_id: str):
    # 0. Check for API key
    if not runtime_config.openrouter_api_key:
        print("❌ Error: OpenRouter API key is not set in config.json.")
        return

    # 1. Initialize the Agent
    print(f"--- Initializing Being: {agent_id} in World: {project_id} ---")
    coder = GodAgent(agent_id=agent_id, project_id=project_id)

    # 2. Define the State and Mission
    mission = "Manifest a Python script named 'prime_finder.py' in your territory that calculates all prime numbers up to 100 and prints them."
    state: GodsState = {
        "project_id": project_id,
        "messages": [HumanMessage(content=mission, name="user")],
        "current_speaker": "user",
        "debate_round": 0,
        "inbox": {},
        "context": mission,
        "next_step": "continue"
    }

    # 3. Process
    print(f"--- Mission Issued: {mission} ---")
    result_state = coder.process(state)

    # 4. Check results
    last_msg = result_state["messages"][-1]
    print(f"\n--- {agent_id}'s Response ---\n")
    print(last_msg.content)

    # 5. Verify local territory
    # The path should now be projects/{project_id}/agents/{agent_id}/prime_finder.py
    target_file = Path("projects") / project_id / "agents" / agent_id / "prime_finder.py"
    
    if target_file.exists():
        print(f"\n✅ SUCCESS: 'prime_finder.py' has been manifested in {target_file}")
        print("--- File Content ---")
        print(target_file.read_text())
    else:
        print(f"\n❌ FAILED: 'prime_finder.py' was not found at {target_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="coder", help="Agent ID")
    parser.add_argument("--project", default="default", help="Project ID")
    args = parser.parse_args()
    
    run_test(args.agent, args.project)
