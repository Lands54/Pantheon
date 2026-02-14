#!/usr/bin/env python
"""
Quick test script to verify agent functionality
"""
import sys
sys.path.insert(0, '.')

from gods.config import runtime_config
from gods.agents.base import GodAgent
from gods.state import GodsState
from langchain_core.messages import HumanMessage

# Load config
import json
with open('config.json', 'r') as f:
    config_data = json.load(f)
    runtime_config.openrouter_api_key = config_data.get('openrouter_api_key', '')
    runtime_config.current_project = config_data.get('current_project', 'test_cli')

print("🧪 Testing Agent Functionality\n")
print(f"API Key: {'SET' if runtime_config.openrouter_api_key else 'NOT SET'}")
print(f"Current Project: {runtime_config.current_project}\n")

# Create agent
agent = GodAgent("genesis", "test_cli")
print(f"✅ Agent created: {agent.agent_id}")
print(f"✅ Brain: {agent.brain}\n")

# Create simple state
state = GodsState(
    messages=[HumanMessage(content="Hello! Please introduce yourself in one sentence.", name="human")],
    next_step="start"
)

print("🤖 Processing message...\n")
result = agent.process(state)

print("\n📝 Result:")
for msg in result["messages"]:
    print(f"[{msg.name}]: {msg.content[:200]}")

print(f"\n✅ Test complete!")
