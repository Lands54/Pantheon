"""
Centralized prompt registry with project-level overrides.
"""
from __future__ import annotations

from pathlib import Path
from string import Template


class PromptRegistry:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or (Path(__file__).resolve().parent / "templates")

    def _resolve(self, name: str, project_id: str | None = None) -> Path:
        filename = f"{name}.txt"
        if project_id:
            project_override = Path("projects") / project_id / "prompts" / filename
            if project_override.exists():
                return project_override
        return self.base_dir / filename

    def get(self, name: str, project_id: str | None = None) -> str:
        path = self._resolve(name, project_id)
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}")
        return path.read_text(encoding="utf-8")

    def render(self, name: str, project_id: str | None = None, **kwargs) -> str:
        raw = self.get(name, project_id)
        return Template(raw).safe_substitute(**kwargs)


prompt_registry = PromptRegistry()
