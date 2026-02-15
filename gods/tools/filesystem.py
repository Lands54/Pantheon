"""
Gods Tools - Filesystem Module
File reading, writing, and manipulation tools with territory isolation.
"""
from pathlib import Path
import json
import os
from langchain.tools import tool

RESERVED_SYSTEM_FILES = {"memory.md", "memory_archive.md", "agent.md", "runtime_state.json"}


def _is_reserved_path(path: Path, agent_territory: Path) -> bool:
    """
    Checks if a given path corresponds to a reserved system file.
    """
    try:
        rel = path.resolve().relative_to(agent_territory.resolve())
    except Exception:
        return False
    return any(part in RESERVED_SYSTEM_FILES for part in rel.parts)


def validate_path(caller_id: str, project_id: str, path: str) -> Path:
    """
    Validates that a requested path is within the agent's project territory.
    """
    project_root = Path(__file__).parent.parent.parent.absolute()
    agent_territory = (project_root / "projects" / project_id / "agents" / caller_id).resolve()
    
    # Ensure directory exists for new agents
    agent_territory.mkdir(parents=True, exist_ok=True)
    
    target_path = (agent_territory / path).resolve()
    
    if not str(target_path).startswith(str(agent_territory)):
        raise PermissionError(f"Divine Restriction: Access to {path} is forbidden. You are confined to your domain.")
    
    return target_path


def _cwd_prefix(agent_territory: Path, message: str) -> str:
    """
    Prefixes a message with the agent's current working directory context.
    """
    return f"[Current CWD: {agent_territory}] Content: {message}"


def _format_fs_error(agent_territory: Path, title: str, reason: str, suggestion: str) -> str:
    """
    Formats a filesystem error message with context and suggestions.
    """
    return _cwd_prefix(
        agent_territory,
        f"{title}: {reason}\nSuggested next step: {suggestion}",
    )


def _normalize_to_territory(path: str, caller_id: str) -> str:
    """
    Removes redundant path prefixes to normalize paths relative to the agent's territory.
    """
    marker = f"/agents/{caller_id}/"
    p = path.replace("\\", "/")
    if marker in p:
        return p.split(marker, 1)[1]
    return path


def _find_name_suggestions(agent_territory: Path, path: str, limit: int = 3) -> list[str]:
    """
    Searches for files with similar names to provide suggestions for missing paths.
    """
    basename = Path(path).name
    if not basename:
        return []
    out = []
    try:
        for cand in agent_territory.rglob(basename):
            rel = cand.relative_to(agent_territory)
            if any(part in RESERVED_SYSTEM_FILES for part in rel.parts):
                continue
            out.append(str(rel))
            if len(out) >= limit:
                break
    except Exception:
        return []
    return out


def _missing_read_hint(path: str, caller_id: str, agent_territory: Path) -> str:
    """
    Generates hints for missing files during a read operation.
    """
    hints = []
    normalized = _normalize_to_territory(path, caller_id)
    if normalized != path:
        hints.append(f"detected extra prefix; try '{normalized}'")

    suggestions = _find_name_suggestions(agent_territory, normalized)
    if suggestions:
        hints.append("found similarly named files: " + ", ".join([f"'{s}'" for s in suggestions]))

    if hints:
        return f" Hint: {'; '.join(hints)}."
    return ""


def _path_lookup_hint(path: str, caller_id: str, agent_territory: Path) -> str:
    """
    Provides suggestions for resolving path errors.
    """
    normalized = _normalize_to_territory(path, caller_id)
    suggestions = _find_name_suggestions(agent_territory, normalized)
    if suggestions:
        return f"Try one of: {', '.join(suggestions)}."
    if normalized != path:
        return f"Try path '{normalized}' (removed redundant prefix)."
    return "Check the path with list_dir('.') first, then retry with a relative path."


@tool
def read_file(path: str, caller_id: str, project_id: str = "default") -> str:
    """Read a scroll from your library. Only your personal scrolls are accessible."""
    try:
        file_path = validate_path(caller_id, project_id, path)
        agent_territory = (Path(__file__).parent.parent.parent.absolute() / "projects" / project_id / "agents" / caller_id).resolve()
        if _is_reserved_path(file_path, agent_territory):
            return _format_fs_error(
                agent_territory,
                "Divine Restriction",
                "Access to system memory files is forbidden.",
                "Do not read memory.md/memory_archive.md/agent.md/runtime_state.json directly. Use normal project files only.",
            )
        if not file_path.exists():
            hint = _missing_read_hint(path, caller_id, agent_territory)
            return _format_fs_error(
                agent_territory,
                "Path Error",
                f"Scroll '{path}' not found.{hint}",
                _path_lookup_hint(path, caller_id, agent_territory),
            )
            
        with open(file_path, "r", encoding="utf-8") as f:
            return _cwd_prefix(agent_territory, f.read())
    except Exception as e:
        project_root = Path(__file__).parent.parent.parent.absolute()
        agent_territory = (project_root / "projects" / project_id / "agents" / caller_id).resolve()
        return _format_fs_error(
            agent_territory,
            "Filesystem Error",
            str(e),
            "Verify the path stays inside your territory and retry.",
        )


@tool
def write_file(path: str, content: str, caller_id: str, project_id: str = "default") -> str:
    """Inscribe a new scroll or overwrite an existing one in your territory."""
    try:
        file_path = validate_path(caller_id, project_id, path)
        agent_territory = (Path(__file__).parent.parent.parent.absolute() / "projects" / project_id / "agents" / caller_id).resolve()
        if _is_reserved_path(file_path, agent_territory):
            return _format_fs_error(
                agent_territory,
                "Divine Restriction",
                "System memory files are managed by the platform.",
                "Write to your own task files, not memory.md/memory_archive.md/agent.md/runtime_state.json.",
            )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return _cwd_prefix(agent_territory, f"Scroll {path} has been inscribed.")
    except Exception as e:
        project_root = Path(__file__).parent.parent.parent.absolute()
        agent_territory = (project_root / "projects" / project_id / "agents" / caller_id).resolve()
        return _format_fs_error(
            agent_territory,
            "Filesystem Error",
            str(e),
            "Check write permissions and ensure the target path is within your territory.",
        )


@tool
def replace_content(path: str, target_content: str, replacement_content: str, caller_id: str, project_id: str = "default") -> str:
    """Refine the scripture within your project territory."""
    try:
        file_path = validate_path(caller_id, project_id, path)
        agent_territory = (Path(__file__).parent.parent.parent.absolute() / "projects" / project_id / "agents" / caller_id).resolve()
        if _is_reserved_path(file_path, agent_territory):
            return _format_fs_error(
                agent_territory,
                "Divine Restriction",
                "System memory files are managed by the platform.",
                "Refine only normal project files.",
            )
        if not file_path.exists():
            return _format_fs_error(
                agent_territory,
                "Path Error",
                f"Scroll {path} not found.",
                _path_lookup_hint(path, caller_id, agent_territory),
            )

        content = file_path.read_text(encoding="utf-8")
        if target_content not in content:
            return _format_fs_error(
                agent_territory,
                "Match Error",
                f"Target sequence not found in {path}.",
                "Read the file first and copy an exact unique snippet as target_content.",
            )

        count = content.count(target_content)
        if count > 1:
            return _format_fs_error(
                agent_territory,
                "Match Error",
                f"Non-unique match ({count} found).",
                "Use a longer unique target_content, or switch to insert_content for anchored edits.",
            )

        new_content = content.replace(target_content, replacement_content)
        file_path.write_text(new_content, encoding="utf-8")
        return _cwd_prefix(agent_territory, f"Sacred scripture {path} has been refined.")
    except Exception as e:
        project_root = Path(__file__).parent.parent.parent.absolute()
        agent_territory = (project_root / "projects" / project_id / "agents" / caller_id).resolve()
        return _format_fs_error(
            agent_territory,
            "Filesystem Error",
            str(e),
            "Retry with a valid relative path and exact target content.",
        )


@tool
def insert_content(path: str, anchor: str, content_to_insert: str, position: str = "after", caller_id: str = "default", project_id: str = "default") -> str:
    """Expand the scripture within your project territory."""
    try:
        file_path = validate_path(caller_id, project_id, path)
        agent_territory = (Path(__file__).parent.parent.parent.absolute() / "projects" / project_id / "agents" / caller_id).resolve()
        if _is_reserved_path(file_path, agent_territory):
            return _format_fs_error(
                agent_territory,
                "Divine Restriction",
                "System memory files are managed by the platform.",
                "Insert content only into normal project files.",
            )
        if not file_path.exists():
            return _format_fs_error(
                agent_territory,
                "Path Error",
                f"Scroll {path} not found.",
                _path_lookup_hint(path, caller_id, agent_territory),
            )

        original_content = file_path.read_text(encoding="utf-8")
        if anchor not in original_content:
            return _format_fs_error(
                agent_territory,
                "Anchor Error",
                f"Anchor '{anchor}' not found.",
                "Read the file and use an exact existing anchor string.",
            )
        
        if original_content.count(anchor) > 1:
            return _format_fs_error(
                agent_territory,
                "Anchor Error",
                "Ambiguous anchor.",
                "Use a longer unique anchor text or narrow the target area first.",
            )

        if position == "after":
            new_content = original_content.replace(anchor, anchor + content_to_insert)
        else:
            new_content = original_content.replace(anchor, content_to_insert + anchor)

        file_path.write_text(new_content, encoding="utf-8")
        return _cwd_prefix(agent_territory, f"New passage manifested in {path} ({position} the anchor).")
    except Exception as e:
        project_root = Path(__file__).parent.parent.parent.absolute()
        agent_territory = (project_root / "projects" / project_id / "agents" / caller_id).resolve()
        return _format_fs_error(
            agent_territory,
            "Filesystem Error",
            str(e),
            "Retry with a valid path, anchor and position ('before' or 'after').",
        )


@tool
def multi_replace(path: str, replacements_json: str, caller_id: str, project_id: str = "default") -> str:
    """Reshape the doctrine within your project territory."""
    try:
        file_path = validate_path(caller_id, project_id, path)
        agent_territory = (Path(__file__).parent.parent.parent.absolute() / "projects" / project_id / "agents" / caller_id).resolve()
        if _is_reserved_path(file_path, agent_territory):
            return _format_fs_error(
                agent_territory,
                "Divine Restriction",
                "System memory files are managed by the platform.",
                "Run multi_replace only on normal project files.",
            )
        replacements = json.loads(replacements_json)
        content = file_path.read_text(encoding="utf-8")
        for rep in replacements:
            target, repl = rep["target"], rep["replacement"]
            if target not in content or content.count(target) > 1:
                return _format_fs_error(
                    agent_territory,
                    "Match Error",
                    f"Refinement failed for '{target}'.",
                    "Ensure each target exists exactly once before running multi_replace.",
                )
            content = content.replace(target, repl)
        file_path.write_text(content, encoding="utf-8")
        return _cwd_prefix(agent_territory, f"Doctrine in {path} reshaped.")
    except Exception as e:
        project_root = Path(__file__).parent.parent.parent.absolute()
        agent_territory = (project_root / "projects" / project_id / "agents" / caller_id).resolve()
        return _format_fs_error(
            agent_territory,
            "Filesystem Error",
            str(e),
            "Validate replacements_json format and target file path, then retry.",
        )


@tool
def list_dir(path: str = ".", caller_id: str = "default", project_id: str = "default") -> str:
    """Survey the chambers within your current project territory."""
    try:
        dir_path = validate_path(caller_id, project_id, path)
        agent_territory = (Path(__file__).parent.parent.parent.absolute() / "projects" / project_id / "agents" / caller_id).resolve()
        if _is_reserved_path(dir_path, agent_territory):
            return _format_fs_error(
                agent_territory,
                "Divine Restriction",
                "Access to system memory files is forbidden.",
                "List normal directories only.",
            )
        if not dir_path.exists():
            return _format_fs_error(
                agent_territory,
                "Path Error",
                f"Path {path} not found.",
                _path_lookup_hint(path, caller_id, agent_territory),
            )
        if not dir_path.is_dir():
            return _format_fs_error(
                agent_territory,
                "Type Error",
                f"Path {path} is not a directory.",
                "Use read_file for files, or pass a directory path to list_dir.",
            )

        items = sorted([
            item for item in os.listdir(dir_path)
            if (not item.startswith('.')) and (item not in RESERVED_SYSTEM_FILES)
        ])
        if not items:
            return _cwd_prefix(agent_territory, "[EMPTY] No visible files or directories.")

        result = [f"{'[CHAMBER]' if (dir_path / item).is_dir() else '[SCROLL]'} {item}" for item in items]
        return _cwd_prefix(agent_territory, "\n".join(result))
    except Exception as e:
        project_root = Path(__file__).parent.parent.parent.absolute()
        agent_territory = (project_root / "projects" / project_id / "agents" / caller_id).resolve()
        return _format_fs_error(
            agent_territory,
            "Filesystem Error",
            str(e),
            "Retry with a valid relative path within your territory.",
        )
