"""
Gods Platform - Runtime Configuration (Persistent)
"""
import os
import json
from pydantic import BaseModel
from typing import Dict, List, Optional
from pathlib import Path

CONFIG_FILE = Path("config.json")

class AgentModelConfig(BaseModel):
    model: str = "google/gemini-2.0-flash-exp:free"

class SystemConfig(BaseModel):
    openrouter_api_key: str = ""
    # agent_id -> specific settings (like model)
    agent_settings: Dict[str, AgentModelConfig] = {}
    # order of active agents
    active_agents: List[str] = []

    def save(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=4))

    @classmethod
    def load(cls):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return cls(**data)
            except Exception as e:
                print(f"Failed to load config: {e}")
        return cls()

# Global runtime instance
runtime_config = SystemConfig.load()

def get_available_agents() -> List[str]:
    """Scan agents/ directory for available agents"""
    agents_dir = Path("agents")
    if not agents_dir.exists():
        return []
    return [d.name for d in agents_dir.iterdir() if d.is_dir()]
