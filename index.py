"""
Gods Platform - Main Entry Point
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

from gods_platform.workflow import create_gods_workflow

def main():
    if len(sys.argv) < 2:
        print("Usage: python index.py \"Your task for the Gods\"")
        sys.exit(1)

    user_task = sys.argv[1]
    
    workflow = create_gods_workflow()
    
    # 初始状态
    from langchain_core.messages import HumanMessage
    initial_state = {
        "messages": [HumanMessage(content=user_task, name="user")],
        "current_speaker": "",
        "debate_round": 0,
        "inbox": {},
        "context": user_task
    }
    
    print(f"🏛️  {user_task}")
    print("="*60)
    
    # 执行工作流
    config = {"configurable": {"thread_id": "gods_debate_1"}}
    
    try:
        for event in workflow.stream(initial_state, config):
            for node, state in event.items():
                print(f"\n[Node: {node}] 已完成处理")
                if "messages" in state and state["messages"]:
                    last_msg = state["messages"][-1]
                    if hasattr(last_msg, 'name'):
                        # 查找当前发言者的最后一条消息（跳过系统观察结果）
                        found = False
                        for msg in reversed(state["messages"]):
                            if getattr(msg, 'name', '') == node:
                                print(f"[{msg.name}]: {msg.content}...")
                                found = True
                                break
                        if not found:
                             print(f"[{last_msg.name}]: {last_msg.content[:200]}...")
    except KeyboardInterrupt:
        print("\n🏛️  众神殿已关闭。")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n❌ 错误: {e}")

if __name__ == "__main__":
    main()
