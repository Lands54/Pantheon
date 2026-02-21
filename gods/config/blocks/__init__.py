from __future__ import annotations

from gods.config.declarations import ConfigBlockDecl, build_default_maps, validate_declaration_blocks
from gods.config.blocks.system import CONFIG_BLOCKS as _SYSTEM_BLOCKS
from gods.config.blocks.project_core import CONFIG_BLOCKS as _PROJECT_CORE_BLOCKS
from gods.config.blocks.angelia import CONFIG_BLOCKS as _ANGELIA_BLOCKS
from gods.config.blocks.context import CONFIG_BLOCKS as _CONTEXT_BLOCKS
from gods.config.blocks.runtime_llm import CONFIG_BLOCKS as _RUNTIME_LLM_BLOCKS
from gods.config.blocks.runtime_exec import CONFIG_BLOCKS as _RUNTIME_EXEC_BLOCKS
from gods.config.blocks.tools import CONFIG_BLOCKS as _TOOLS_BLOCKS
from gods.config.blocks.debug import CONFIG_BLOCKS as _DEBUG_BLOCKS
from gods.config.blocks.deprecated import CONFIG_BLOCKS as _DEPRECATED_BLOCKS
from gods.config.blocks.agent_overrides import CONFIG_BLOCKS as _AGENT_BLOCKS


ALL_CONFIG_BLOCKS: list[ConfigBlockDecl] = (
    _SYSTEM_BLOCKS
    + _PROJECT_CORE_BLOCKS
    + _ANGELIA_BLOCKS
    + _CONTEXT_BLOCKS
    + _RUNTIME_LLM_BLOCKS
    + _RUNTIME_EXEC_BLOCKS
    + _TOOLS_BLOCKS
    + _DEBUG_BLOCKS
    + _DEPRECATED_BLOCKS
    + _AGENT_BLOCKS
)

validate_declaration_blocks(ALL_CONFIG_BLOCKS)

DEFAULT_MAPS = build_default_maps(ALL_CONFIG_BLOCKS)
SYSTEM_DEFAULTS = DEFAULT_MAPS["system"]
PROJECT_DEFAULTS = DEFAULT_MAPS["project"]
AGENT_DEFAULTS = DEFAULT_MAPS["agent"]

__all__ = [
    "ALL_CONFIG_BLOCKS",
    "SYSTEM_DEFAULTS",
    "PROJECT_DEFAULTS",
    "AGENT_DEFAULTS",
]
