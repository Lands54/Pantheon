"""
Gods Tools - Execution Module
Command execution tools with security restrictions.
"""
import subprocess
from pathlib import Path
from langchain.tools import tool
from .filesystem import validate_path


@tool
def run_command(command: str, caller_id: str = "default", project_id: str = "default") -> str:
    """Run a shell command within your project territory."""
    blacklist = ["rm", "mv", "chmod", "chown", "sudo", "su", "curl", "wget", "apt", "pip", "kill"]
    cmd_parts = command.lower().split()
    for forbidden in blacklist:
        if forbidden in cmd_parts:
            return f"Divine Restriction: Forbidden sorcery '{forbidden}'."

    if any(char in command for char in [";", "&", "|", ">", "<", "`", "$"]):
        return "Divine Restriction: Complex incantations forbidden."

    try:
        territory = validate_path(caller_id, project_id, ".")
        result = subprocess.run(command.split(), cwd=territory, capture_output=True, text=True, timeout=5.0)
        return f"Manifestation Result:\nSTDOUT: {result.stdout[:2000]}\nSTDERR: {result.stderr[:2000]}"
    except Exception as e:
        return f"Manifestation Failed: {str(e)}"
