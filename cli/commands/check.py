"""
CLI Check Command - Check agent responses and activity
"""
import requests
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
    memory_file = agent_dir / "memory.md"
    inbox_file = agent_dir / "inbox.jsonl"
    
    print(f"\n📬 Checking {agent_id}'s activity in {pid}...\n")
    
    # Show inbox status
    if inbox_file.exists():
        with open(inbox_file, 'r') as f:
            lines = f.readlines()
            pending = len(lines)
            print(f"📥 Inbox: {pending} pending message(s)")
    else:
        print(f"📥 Inbox: Empty")
    
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
    
    # Check for prayers (messages to human)
    try:
        res = requests.get(f"{base_url}/prayers/check")
        prayers = res.json().get("prayers", [])
        
        if prayers:
            print(f"\n🙏 Messages to You:\n")
            for p in prayers:
                if p.get('from') == agent_id:
                    print(f"   [{p.get('from')}]: {p.get('content')}")
        else:
            print(f"\n🙏 No messages to you yet")
    except:
        pass
    
    print(f"\n💡 Tip: Use './temple.sh confess {agent_id} \"your message\"' to send a message")
    print(f"💡 Tip: View full memory with 'cat projects/{pid}/agents/{agent_id}/memory.md'")
