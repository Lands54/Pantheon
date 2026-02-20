import os
import sys
import shutil
import time
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from gods.agents.base import GodAgent
from gods.mnemosyne.facade import record_intent
from gods.mnemosyne.contracts import MemoryIntent
from gods.chaos.snapshot import build_resource_snapshot
from gods.janus.service import janus_service
from gods.metis.contracts import RuntimeEnvelope

def test_drive():
    project_id = "test_drive_v2"
    agent_id = "demonstrator"
    
    # Clean up and setup
    shutil.rmtree(f"projects/{project_id}", ignore_errors=True)
    
    # 1. Setup profile and basics
    profile_dir = Path(f"projects/{project_id}/mnemosyne/agent_profiles")
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / f"{agent_id}.md").write_text("# DEMO AGENT\nFocus: Architecture Verification.")
    
    agent = GodAgent(agent_id=agent_id, project_id=project_id)
    
    print("\n--- [1] Recording Initial Intents ---")
    
    # Simple intents to avoid schema hell in scripts
    # Self Memory
    record_intent(MemoryIntent(
        intent_key="llm.response",
        project_id=project_id,
        agent_id=agent_id,
        source_kind="llm",
        payload={"phase": "react_graph", "content": "I am thinking about the semantics refactors."},
        timestamp=time.time() - 10
    ))
    
    # Inbox
    record_intent(MemoryIntent(
        intent_key="inbox.received.unread",
        project_id=project_id,
        agent_id=agent_id,
        source_kind="inbox",
        payload={
            "title": "Query", 
            "sender": "human", 
            "message_id": "m_99", 
            "msg_type": "text",
            "content": "Hello! Can you see your own memory?",
            "payload": {}
        },
        fallback_text="[MAIL] From human: Hello!",
        timestamp=time.time()
    ))

    print("Intents recorded successfully.")
    
    # 3. Build Snapshot
    state = {"project_id": project_id, "agent_id": agent_id, "strategy": "react_graph", "cards": []}
    snapshot = build_resource_snapshot(agent, state)
    
    # 4. Use Janus to build the Sequential Prompt
    print("\n--- [2] Recomposing Context (Mindless Scheme) ---")
    
    envelope = RuntimeEnvelope(
        strategy="react_graph",
        state=state,
        resource_snapshot=snapshot,
        policy={}
    )
    
    messages, report = janus_service.build_llm_messages_from_envelope(
        envelope=envelope,
        directives="Be concise.",
        local_memory="Archive: Seeded at 2026.",
        inbox_hint="Check your inbox.",
        tools_desc="Tool1, Tool2"
    )
    
    print(f"Strategy used: {report['strategy_used']}")
    
    # 5. Display the blocks
    print("\n--- [3] Verifying Sequential Block Order ---")
    blocks = [str(m.content) for m in messages]
    for i, content in enumerate(blocks):
        line = content.split('\n')[0]
        print(f"Block {i:02} (First 60 chars): {line[:60]}...")

    # Final logic check
    print("\n--- [4] Logic Check ---")
    assert "[PROFILE]" in blocks[0]
    print("SUCCESS: PROFILE is at head.")
    
    # Finding the intents
    found_self = any("I am thinking" in b for b in blocks)
    found_inbox = any("From human: Hello!" in b for b in blocks)
    assert found_self and found_inbox, "Both self-memory and inbox should be in context."
    print("SUCCESS: Self-memory and Inbox are both present.")

    assert "## AVAILABLE TOOLS" in blocks[-2]
    assert "## LOCAL MEMORY" in blocks[-1]
    print("SUCCESS: Tools and Archive are at tail.")

    print("\nALL VERIFICATIONS PASSED.")

if __name__ == "__main__":
    test_drive()
