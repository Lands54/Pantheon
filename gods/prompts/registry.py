"""
Centralized prompt registry with project-level overrides.
"""
from __future__ import annotations

from pathlib import Path
from string import Template


class PromptRegistry:
    """
    Manager for loading and rendering prompt templates with project-level override support.
    """
    def __init__(self, base_dir: Path | None = None):
        """
        Initializes the prompt registry with an optional base templates directory.
        """
        self.base_dir = base_dir or (Path(__file__).resolve().parent / "templates")

    def _resolve(self, name: str, project_id: str | None = None) -> Path:
        """
        Resolves the file path for a prompt template, checking for project overrides first.
        """
        filename = f"{name}.txt"
        if project_id:
            project_override = Path("projects") / project_id / "prompts" / filename
            if project_override.exists():
                return project_override
        return self.base_dir / filename

    def get(self, name: str, project_id: str | None = None) -> str:
        """
        Loads the raw text of a prompt template.
        """
        path = self._resolve(name, project_id)
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}")
        return path.read_text(encoding="utf-8")

    def render(self, name: str, project_id: str | None = None, **kwargs) -> str:
        """
        Renders a prompt template by substituting variables with provided keyword arguments.
        """
        raw = self.get(name, project_id)
        return Template(raw).safe_substitute(**kwargs)


prompt_registry = PromptRegistry()
