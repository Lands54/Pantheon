
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from gods.mnemosyne.facade import record_intent
from gods.chaos.snapshot import build_resource_snapshot
from gods.janus.service import janus_service
from gods.janus.models import ContextBuildRequest
from gods.config import runtime_config

class MockAgent:
    def __init__(self, project_id, agent_id):
        self.project_id = project_id
        self.agent_id = agent_id

def test_compression():
    project_id = "default"
    agent_id = "compressor"
    agent = MockAgent(project_id, agent_id)
    
    print(f"--- Testing compression for {agent_id} ---")
    
    # 1. Clean up old intents if any (manual)
    from gods.mnemosyne.contracts import MemoryIntent
    
    # 2. Record several intents
    for i in range(20):
        intent = MemoryIntent(
            project_id=project_id,
            agent_id=agent_id,
            intent_key="event.manual",
            payload={"event_id": f"evt-{i}", "event_type": "manual", "priority": 1, "attempt": 1, "max_attempts": 1, "stage": "test", "content": "This is a long string to consume tokens. " * 50, "payload": {}},
            fallback_text="This is a long string to consume tokens. " * 50,
            source_kind="event"
        )
        record_intent(intent)
   
    # 3. Build snapshot
    snapshot = build_resource_snapshot(agent, {"cards": []})
    
    if hasattr(snapshot, "context_materials") and hasattr(snapshot.context_materials, "cards"):
        print(f"Context cards built: {len(snapshot.context_materials.cards)}")
    else:
        print("No cards found in materials.")
        
    # 4. Trigger Janus with low threshold
    class MockEnvelope:
        def __init__(self, snapshot):
            self.resource_snapshot = snapshot
            self.state = {"project_id": project_id, "agent_id": agent_id}
            self.strategy = "sequential_v1"

    env = MockEnvelope(snapshot)
    
    # Temporarily override config for testing via mock
    import gods.janus.service
    old_resolve = gods.janus.service.resolve_context_cfg
    def mock_resolve(*args):
        cfg = old_resolve(*args)
        cfg["token_budget_chronicle_trigger"] = 500
        cfg["n_recent"] = 5
        cfg["strategy"] = "sequential_v1"
        return cfg
    gods.janus.service.resolve_context_cfg = mock_resolve
    
    print("Building LLM messages (should trigger compression)...")
    messages, report = janus_service.build_llm_messages_from_envelope(
        agent=None, # It will fallback to GodBrain(agent_id, project_id)
        envelope=env,
        directives="Be compressed.",
        local_memory="",
        inbox_hint="",
        tools_desc=""
    )
    
    print(f"Strategy used: {report.get('strategy_used')}")
    print(f"Compression preview: {report.get('preview', {}).get('compression')}")
    
    # Check if a derived card exists in the output
    summary_content = next((str(m.content) for m in messages if hasattr(m, "content") and "[HISTORY_SUMMARY]" in str(m.content)), None)
    has_summary = summary_content is not None
    print(f"Has [HISTORY_SUMMARY] in messages: {has_summary}")
    
    if has_summary:
        print("SUCCESS: Compression was triggered and summary was included.")
        print("\n--- ACTUAL SUMMARY RETURNED BY LLM ---")
        print(summary_content)
        print("--------------------------------------")
    else:
        print("FAILURE: Compression was not detected in output.")

if __name__ == "__main__":
    test_compression()
