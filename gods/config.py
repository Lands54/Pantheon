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
    model: str = "stepfun/step-3.5-flash:free"
    disabled_tools: List[str] = []

class ProjectConfig(BaseModel):
    name: Optional[str] = None
    active_agents: List[str] = ["genesis"]
    agent_settings: Dict[str, AgentModelConfig] = {
        "genesis": AgentModelConfig()
    }
    simulation_enabled: bool = False
    simulation_interval_min: int = 10
    simulation_interval_max: int = 40
    summarize_threshold: int = 12
    summarize_keep_count: int = 5
    # Command execution governance
    command_max_parallel: int = 2
    command_timeout_sec: int = 60
    command_max_memory_mb: int = 512
    command_max_cpu_sec: int = 15
    command_max_output_chars: int = 4000

class SystemConfig(BaseModel):
    openrouter_api_key: str = ""
    current_project: str = "default"
    # project_id -> project settings
    projects: Dict[str, ProjectConfig] = {
        "default": ProjectConfig(name="Default World")
    }

    def save(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=4))

    @classmethod
    def load(cls):
        if not CONFIG_FILE.exists():
            return cls()
        
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Migration logic: if 'projects' is missing, it's an old config
            if "projects" not in data:
                print("--- MIGRATING OLD CONFIG TO PROJECT STRUCTURE ---")
                old_active = data.get("active_agents", ["genesis"])
                old_settings = data.get("agent_settings", {"genesis": {}})
                
                # Create a default project with old settings
                default_proj = ProjectConfig(
                    name="Default World",
                    active_agents=old_active,
                    agent_settings={k: AgentModelConfig(**v) if isinstance(v, dict) else v for k, v in old_settings.items()},
                    simulation_enabled=data.get("simulation_enabled", False),
                    simulation_interval_min=data.get("simulation_interval_min", 10),
                    simulation_interval_max=data.get("simulation_interval_max", 40),
                    summarize_threshold=data.get("summarize_threshold", 12),
                    summarize_keep_count=data.get("summarize_keep_count", 5)
                )
                
                new_cfg = cls(
                    openrouter_api_key=data.get("openrouter_api_key", ""),
                    current_project="default",
                    projects={"default": default_proj}
                )
                new_cfg.save() # Save the migrated version
                return new_cfg
            
            return cls(**data)
        except Exception as e:
            print(f"Failed to load/migrate config: {e}")
            return cls()

# Global runtime instance
runtime_config = SystemConfig.load()

def get_current_project() -> ProjectConfig:
    return runtime_config.projects.get(runtime_config.current_project, ProjectConfig(name="Safety", active_agents=[]))

def get_available_agents(project_id: str = None) -> List[str]:
    """Scan projects/{project_id}/agents/ directory for available agents"""
    if not project_id:
        project_id = runtime_config.current_project
        
    agents_dir = Path("projects") / project_id / "agents"
    if not agents_dir.exists():
        # Fallback for old structure if project is default
        if project_id == "default":
            old_dir = Path("agents")
            if old_dir.exists(): return [d.name for d in old_dir.iterdir() if d.is_dir()]
        return []
    return [d.name for d in agents_dir.iterdir() if d.is_dir()]

# Global runtime instance
runtime_config = SystemConfig.load()
