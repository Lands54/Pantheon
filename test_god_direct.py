#!/usr/bin/env python3
import sys
from pathlib import Path

# 正确设置路径
sys.path.insert(0, str(Path(__file__).parent))

from shared.god_dna import GodEntity

# 测试 Genesis
agent_dir = Path("agents/genesis")
god = GodEntity(agent_dir)

print(f"Agent ID: {god.agent_id}")
print(f"检查感知...")
msg_count = god.perceive()
print(f"消息数量: {msg_count}")

if msg_count > 0:
    print("触发思考...")
    god.think_and_act(msg_count)
    print("完成！")
else:
    print("没有消息")
