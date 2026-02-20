import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from gods.agents.base import GodAgent
from gods.chaos.snapshot import build_resource_snapshot
from gods.janus.service import janus_service
from gods.janus.models import ContextBuildRequest
from gods.janus.registry import get_strategy
from gods.janus.context_policy import resolve_context_cfg

def show_detailed_blocks():
    project_id = "Pantheon"
    agent_id = "coder"
    
    agent = GodAgent(agent_id=agent_id, project_id=project_id)
    state = {"project_id": project_id, "agent_id": agent_id, "strategy": "react_graph"}
    
    # 1. Build Snapshot
    snapshot = build_resource_snapshot(agent, state)
    
    # 2. Prepare Janus Request
    cfg = resolve_context_cfg(project_id, agent_id)
    req = ContextBuildRequest(
        project_id=project_id,
        agent_id=agent_id,
        state=state,
        directives=agent._build_behavior_directives(),
        local_memory=agent._load_local_memory(),
        inbox_hint=agent._build_inbox_context_hint(),
        phase_name="react_graph",
        tools_desc=agent._render_tools_desc("llm_think"),
        context_materials=snapshot.context_materials,
        context_cfg=cfg
    )
    
    # 3. Use the strategy to get RAW blocks
    strategy = get_strategy("sequential_v1")
    result = strategy.build(req)
    
    print("\n" + "="*80)
    print("      JANUS SEQUENTIAL STRATEGY: RAW SYSTEM BLOCKS PREVIEW")
    print("="*80 + "\n")
    
    for i, block in enumerate(result.system_blocks):
        title = "UNKNOWN"
        first_line = block.split("\n")[0].strip()
        
        # Heuristic to identify block types for the user
        if "[PROFILE]" in block: title = "FIXED HEAD: PROFILE"
        elif "[DIRECTIVES]" in block: title = "FIXED HEAD: DIRECTIVES"
        elif "[TASK_STATE]" in block: title = "FIXED HEAD: TASK STATE"
        elif "## AVAILABLE TOOLS" in block: title = "FIXED TAIL: TOOLS"
        elif "## LOCAL MEMORY" in block: title = "FIXED TAIL: ARCHIVE"
        elif "material.mailbox" in str(block): title = "FIXED TAIL: MAILBOX"
        elif "[MAIL]" in block or "llm.response" in block or "intent.seq" in block: title = "MEMORY: CONTEXT CARD"
        else: title = f"BLOCK: {first_line[:40]}..."

        print(f"--- [#{i:02} | {title}] ---")
        # Print first few lines to keep it readable but informative
        lines = block.split("\n")
        preview_lines = lines[:10]
        for line in preview_lines:
            print(f"    {line}")
        if len(lines) > 10:
            print(f"    ... ({len(lines)-10} more lines)")
        print()

    print("="*80)
    print(f"TOTAL BLOCKS: {len(result.system_blocks)}")
    print("="*80 + "\n")

if __name__ == "__main__":
    show_detailed_blocks()
