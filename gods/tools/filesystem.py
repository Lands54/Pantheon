"""
Gods Tools - Filesystem Module
File reading, writing, and manipulation tools with territory isolation.
"""
from pathlib import Path
import json
import os
from langchain.tools import tool

RESERVED_SYSTEM_FILES = {"memory.md", "memory_archive.md"}


def _is_reserved_path(path: Path, agent_territory: Path) -> bool:
    """
    Disallow agent tools from directly accessing system-managed memory files.
    """
    try:
        rel = path.resolve().relative_to(agent_territory.resolve())
    except Exception:
        return False
    return any(part in RESERVED_SYSTEM_FILES for part in rel.parts)


def validate_path(caller_id: str, project_id: str, path: str) -> Path:
    """Ensure the path is strictly within projects/{project_id}/agents/{caller_id}/"""
    project_root = Path(__file__).parent.parent.parent.absolute()
    agent_territory = (project_root / "projects" / project_id / "agents" / caller_id).resolve()
    
    # Ensure directory exists for new agents
    agent_territory.mkdir(parents=True, exist_ok=True)
    
    target_path = (agent_territory / path).resolve()
    
    if not str(target_path).startswith(str(agent_territory)):
        raise PermissionError(f"Divine Restriction: Access to {path} is forbidden. You are confined to your domain.")
    
    return target_path


@tool
def read_file(path: str, caller_id: str, project_id: str = "default") -> str:
    """Read a scroll from your library. Only your personal scrolls are accessible."""
    try:
        file_path = validate_path(caller_id, project_id, path)
        agent_territory = (Path(__file__).parent.parent.parent.absolute() / "projects" / project_id / "agents" / caller_id).resolve()
        if _is_reserved_path(file_path, agent_territory):
            return "Divine Restriction: Access to system memory files is forbidden."
        if not file_path.exists():
            return f"Error: Scroll {path} not found."
            
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Divine Restriction: {str(e)}"


@tool
def write_file(path: str, content: str, caller_id: str, project_id: str = "default") -> str:
    """Inscribe a new scroll or overwrite an existing one in your territory."""
    try:
        file_path = validate_path(caller_id, project_id, path)
        agent_territory = (Path(__file__).parent.parent.parent.absolute() / "projects" / project_id / "agents" / caller_id).resolve()
        if _is_reserved_path(file_path, agent_territory):
            return "Divine Restriction: System memory files are managed by the platform."
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Scroll {path} has been inscribed."
    except Exception as e:
        return f"Divine Restriction: {str(e)}"


@tool
def replace_content(path: str, target_content: str, replacement_content: str, caller_id: str, project_id: str = "default") -> str:
    """Refine the scripture within your project territory."""
    try:
        file_path = validate_path(caller_id, project_id, path)
        agent_territory = (Path(__file__).parent.parent.parent.absolute() / "projects" / project_id / "agents" / caller_id).resolve()
        if _is_reserved_path(file_path, agent_territory):
            return "Divine Restriction: System memory files are managed by the platform."
        if not file_path.exists():
            return f"Error: Scroll {path} not found."

        content = file_path.read_text(encoding="utf-8")
        if target_content not in content:
            return f"Error: Target sequence not found in {path}."

        count = content.count(target_content)
        if count > 1:
            return f"Error: Non-unique match ({count} found)."

        new_content = content.replace(target_content, replacement_content)
        file_path.write_text(new_content, encoding="utf-8")
        return f"Sacred scripture {path} has been refined."
    except Exception as e:
        return f"Divine Restriction: {str(e)}"


@tool
def insert_content(path: str, anchor: str, content_to_insert: str, position: str = "after", caller_id: str = "default", project_id: str = "default") -> str:
    """Expand the scripture within your project territory."""
    try:
        file_path = validate_path(caller_id, project_id, path)
        agent_territory = (Path(__file__).parent.parent.parent.absolute() / "projects" / project_id / "agents" / caller_id).resolve()
        if _is_reserved_path(file_path, agent_territory):
            return "Divine Restriction: System memory files are managed by the platform."
        if not file_path.exists():
            return f"Error: Scroll {path} not found."

        original_content = file_path.read_text(encoding="utf-8")
        if anchor not in original_content:
            return f"Error: Anchor '{anchor}' not found."
        
        if original_content.count(anchor) > 1:
            return f"Error: Ambiguous anchor."

        if position == "after":
            new_content = original_content.replace(anchor, anchor + content_to_insert)
        else:
            new_content = original_content.replace(anchor, content_to_insert + anchor)

        file_path.write_text(new_content, encoding="utf-8")
        return f"New passage manifested in {path} ({position} the anchor)."
    except Exception as e:
        return f"Divine Restriction: {str(e)}"


@tool
def multi_replace(path: str, replacements_json: str, caller_id: str, project_id: str = "default") -> str:
    """Reshape the doctrine within your project territory."""
    try:
        file_path = validate_path(caller_id, project_id, path)
        agent_territory = (Path(__file__).parent.parent.parent.absolute() / "projects" / project_id / "agents" / caller_id).resolve()
        if _is_reserved_path(file_path, agent_territory):
            return "Divine Restriction: System memory files are managed by the platform."
        replacements = json.loads(replacements_json)
        content = file_path.read_text(encoding="utf-8")
        for rep in replacements:
            target, repl = rep["target"], rep["replacement"]
            if target not in content or content.count(target) > 1:
                return f"Error: Refinement failed for '{target}'."
            content = content.replace(target, repl)
        file_path.write_text(content, encoding="utf-8")
        return f"Doctrine in {path} reshaped."
    except Exception as e:
        return f"Divine Restriction: {str(e)}"


@tool
def list_dir(path: str = ".", caller_id: str = "default", project_id: str = "default") -> str:
    """Survey the chambers within your current project territory."""
    try:
        dir_path = validate_path(caller_id, project_id, path)
        agent_territory = (Path(__file__).parent.parent.parent.absolute() / "projects" / project_id / "agents" / caller_id).resolve()
        if _is_reserved_path(dir_path, agent_territory):
            return "Divine Restriction: Access to system memory files is forbidden."
        if not dir_path.exists():
            return f"Error: Path {path} not found."
        if not dir_path.is_dir():
            return f"Error: Path {path} is not a directory."

        items = sorted([
            item for item in os.listdir(dir_path)
            if (not item.startswith('.')) and (item not in RESERVED_SYSTEM_FILES)
        ])
        if not items:
            return "[EMPTY] No visible files or directories."

        result = [f"{'[CHAMBER]' if (dir_path / item).is_dir() else '[SCROLL]'} {item}" for item in items]
        return "\n".join(result)
    except Exception as e:
        return f"Divine Restriction: {str(e)}"
