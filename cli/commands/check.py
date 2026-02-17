"""
CLI Check Command - Check agent responses and activity
"""
import requests
import json
from pathlib import Path
from cli.utils import get_base_url


def cmd_check(args):
    """Check agent responses and recent activity."""
    base_url = get_base_url()
    
    # Get current project
    try:
        res = requests.get(f"{base_url}/config")
        data = res.json()
        pid = args.project or data.get("current_project", "default")
    except:
        pid = "default"
    
    agent_id = args.agent_id
    
    # Check if agent exists
    agent_dir = Path(f"projects/{pid}/agents/{agent_id}")
    if not agent_dir.exists():
        print(f"❌ Agent '{agent_id}' not found in project '{pid}'")
        return
    
    # Read agent's memory
    memory_file = Path(f"projects/{pid}/mnemosyne/chronicles/{agent_id}.md")
    
    print(f"\n📬 Checking {agent_id}'s activity in {pid}...\n")

    # Scheduler status
    try:
        status_res = requests.get(f"{base_url}/agents/status", params={"project_id": pid})
        status_data = status_res.json()
        for item in status_data.get("agents", []):
            if item.get("agent_id") == agent_id:
                import datetime
                lp = item.get("last_pulse_at", 0) or 0
                ne = item.get("next_eligible_at", 0) or 0
                lp_s = datetime.datetime.fromtimestamp(lp).strftime("%Y-%m-%d %H:%M:%S") if lp > 0 else "N/A"
                ne_s = datetime.datetime.fromtimestamp(ne).strftime("%Y-%m-%d %H:%M:%S") if ne > 0 else "N/A"
                print(f"🧭 Scheduler: {item.get('status', 'unknown')}")
                print(f"   Last Pulse: {lp_s}")
                print(f"   Next Eligible: {ne_s}")
                print(f"   Empty Cycles: {item.get('empty_cycles', 0)}")
                print(f"   Pending Inbox: {item.get('has_pending_inbox', False)}")
                break
    except Exception:
        pass
    
    # Show wake queue status (Angelia inbox_event)
    try:
        queued_res = requests.get(
            f"{base_url}/angelia/events",
            params={
                "project_id": pid,
                "agent_id": agent_id,
                "event_type": "inbox_event",
                "state": "queued",
                "limit": 500,
            },
            timeout=4,
        )
        processing_res = requests.get(
            f"{base_url}/angelia/events",
            params={
                "project_id": pid,
                "agent_id": agent_id,
                "event_type": "inbox_event",
                "state": "processing",
                "limit": 500,
            },
            timeout=4,
        )
        queued_n = len((queued_res.json() or {}).get("items", []))
        processing_n = len((processing_res.json() or {}).get("items", []))
        print(f"📥 Wake Queue(inbox_event): queued={queued_n}, processing={processing_n}")
    except Exception:
        print("📥 Wake Queue: unavailable")
    
    # Show read receipts
    read_path = Path(f"projects/{pid}/buffers/{agent_id}_read.jsonl")
    if read_path.exists():
        print(f"\n📖 Read Receipts (Acknowledged by Agent):")
        from datetime import datetime
        with open(read_path, 'r') as f:
            read_lines = f.readlines()[-5:] # Show last 5 read receipts
            for line in read_lines:
                if line.strip():
                    msg = json.loads(line)
                    read_time = datetime.fromtimestamp(msg.get("read_at", 0)).strftime("%Y-%m-%d %H:%M:%S")
                    sender = msg.get("from", "unknown")
                    content = msg.get("content", "")[:50]
                    print(f"   ✅ [{read_time}] Read message from {sender}: \"{content}...\"")
    
    # Show recent memory entries
    if memory_file.exists():
        print(f"\n💭 Recent Activity (last 10 entries):\n")
        with open(memory_file, 'r') as f:
            content = f.read()
            
        # Split by entry markers
        entries = content.split('### 📖 Entry')
        recent_entries = entries[-11:]  # Get last 10 entries (plus empty first split)
        
        for entry in recent_entries[1:]:  # Skip first empty split
            lines = entry.strip().split('\n')
            if lines:
                timestamp = lines[0].strip('[]').strip()
                content_lines = [l for l in lines[1:] if l.strip() and not l.startswith('---')]
                content_preview = '\n'.join(content_lines[:3])  # First 3 lines
                
                print(f"⏰ {timestamp}")
                print(f"   {content_preview}")
                if len(content_lines) > 3:
                    print(f"   ... ({len(content_lines) - 3} more lines)")
                print()
    else:
        print(f"\n💭 No memory file found")

    # Show recent pulse debug traces
    trace_file = agent_dir / "debug" / "pulse_trace.jsonl"
    if trace_file.exists():
        print(f"\n🪵 Pulse Trace (last 3):")
        try:
            lines = trace_file.read_text(encoding="utf-8").splitlines()[-3:]
            for line in lines:
                if not line.strip():
                    continue
                item = json.loads(line)
                pulse_id = item.get("pulse_id", "unknown")
                reason = item.get("reason", "unknown")
                duration = item.get("duration_sec", 0)
                events = item.get("events", [])
                end = events[-1] if events else {}
                next_step = end.get("next_step", "")
                terminal = end.get("terminal_reason", "")
                print(f"   pulse={pulse_id} reason={reason} duration={duration}s")
                print(f"      next_step={next_step} terminal={terminal} events={item.get('event_count', 0)}")
        except Exception as e:
            print(f"   (trace parse failed: {e})")

    llm_trace_file = agent_dir / "debug" / "llm_io.jsonl"
    if llm_trace_file.exists():
        print(f"\n🧠 LLM IO Trace (last 3):")
        try:
            lines = llm_trace_file.read_text(encoding="utf-8").splitlines()[-3:]
            for line in lines:
                if not line.strip():
                    continue
                item = json.loads(line)
                mode = item.get("mode", "")
                model = item.get("model", "")
                pulse_id = item.get("pulse_id", "")
                has_resp = "response" in item
                err = item.get("error", "")
                print(f"   pulse={pulse_id} mode={mode} model={model} response={has_resp} error={bool(err)}")
        except Exception as e:
            print(f"   (llm trace parse failed: {e})")
    
    print(f"\n💡 Tip: Use './temple.sh confess {agent_id} \"your message\"' to send a message")
    print(f"💡 Tip: View full memory with 'cat projects/{pid}/mnemosyne/chronicles/{agent_id}.md'")
