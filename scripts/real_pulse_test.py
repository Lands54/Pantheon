import os
import sys
import json
import time
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from gods.agents.base import GodAgent
from gods.mnemosyne.facade import record_intent
from gods.mnemosyne.contracts import MemoryIntent
from gods.config import runtime_config

def run_real_pulse():
    # Use a real project/agent from the codebase
    project_id = "Pantheon"
    agent_id = "coder"
    
    # Ensure project exists in runtime_config
    runtime_config.current_project = project_id
    
    print(f"--- Triggering Real Pulse for {agent_id} in {project_id} ---")
    
    # 1. Inject a message to the agent to give it something to think about
    msg_id = f"test_{int(time.time())}"
    record_intent(MemoryIntent(
        intent_key="inbox.received.unread",
        project_id=project_id,
        agent_id=agent_id,
        source_kind="inbox",
        payload={
            "title": "System Check", 
            "sender": "Antigravity", 
            "message_id": msg_id, 
            "msg_type": "text",
            "content": "Antigravity requested an architecture verification. Please reflect on your current context strategy.",
            "payload": {}
        },
        fallback_text=f"[MAIL] Verification request: {msg_id}"
    ))
    
    # 2. Instantiate agent and process
    agent = GodAgent(agent_id=agent_id, project_id=project_id)
    
    # Mock a starting state
    state = {
        "project_id": project_id,
        "agent_id": agent_id,
        "messages": [],
        "loop_count": 0,
        "max_rounds": 1
    }
    
    print("Running agent.process()...")
    # This will trigger the full pipeline: Chaos -> Metis -> Janus -> Brain
    try:
        final_state = agent.process(state)
        print("Pulse completed successfully.")
    except Exception as e:
        print(f"Pulse failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Locate the build report
    report_dir = Path(f"projects/{project_id}/mnemosyne/context_reports/{agent_id}")
    if not report_dir.exists():
         print("Error: Context report directory not found.")
         return

    reports = sorted(list(report_dir.glob("*.json")), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        print("Error: No context reports generated.")
        return

    latest_report_path = reports[0]
    print(f"\n--- Latest Context Report: {latest_report_path.name} ---")
    
    with open(latest_report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    print(f"Strategy Used: {report.get('strategy_used')}")
    
    # Show the preview of blocks
    preview = report.get("preview", {})
    print(f"Blocks assembled: {len(report.get('system_blocks', [])) if 'system_blocks' in report else 'Check preview'}")
    
    # If build_llm_messages_from_envelope records correctly, we might see the blocks
    # Note: SequentialV1Strategy returns ContextBuildResult with system_blocks
    blocks = report.get('system_blocks', [])
    if not blocks:
         # Some reports might only store metadata. Let's check the preview if available.
         print("Preview metrics:", preview)
    else:
        for i, b in enumerate(blocks):
            clean_b = b[:100].replace("\n", " ")
            print(f"Block {i:02}: {clean_b}...")

if __name__ == "__main__":
    run_real_pulse()
