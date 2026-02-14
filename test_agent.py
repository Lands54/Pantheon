#!/usr/bin/env python
"""
Quick test script to verify agent functionality
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, '.')

from gods.config import runtime_config
from gods.agents.base import GodAgent
from langchain_core.messages import HumanMessage

def main():
    config_path = Path("config.json")
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            config_data = json.load(f)
            runtime_config.openrouter_api_key = config_data.get("openrouter_api_key", "")
            runtime_config.current_project = config_data.get("current_project", "test_cli")

    print("🧪 Testing Agent Functionality\n")
    print(f"API Key: {'SET' if runtime_config.openrouter_api_key else 'NOT SET'}")
    print(f"Current Project: {runtime_config.current_project}\n")

    agent = GodAgent("genesis", "test_cli")
    print(f"✅ Agent created: {agent.agent_id}")
    print(f"✅ Brain: {agent.brain}\n")

    state = {
        "project_id": "test_cli",
        "messages": [HumanMessage(content="Hello! Please introduce yourself in one sentence.", name="human")],
        "context": "quick test",
        "next_step": "start",
    }

    print("🤖 Processing message...\n")
    result = agent.process(state)

    print("\n📝 Result:")
    for msg in result["messages"]:
        print(f"[{msg.name}]: {msg.content[:200]}")

    print("\n✅ Test complete!")


if __name__ == "__main__":
    main()
