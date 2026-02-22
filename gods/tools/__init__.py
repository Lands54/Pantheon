"""Unified tool exports with lazy loading to avoid heavy import side effects."""
from __future__ import annotations

from typing import Iterator
import importlib

# name -> (module_path, attr_name)
_TOOL_EXPORTS: dict[str, tuple[str, str]] = {
    "check_inbox": ("gods.tools.comm_inbox", "check_inbox"),
    "check_outbox": ("gods.tools.comm_inbox", "check_outbox"),
    "send_message": ("gods.tools.comm_human", "send_message"),
    "finalize": ("gods.tools.comm_human", "finalize"),
    "post_to_synod": ("gods.tools.comm_human", "post_to_synod"),
    "abstain_from_synod": ("gods.tools.comm_human", "abstain_from_synod"),
    "list_agents": ("gods.tools.comm_human", "list_agents"),
    "council_status": ("gods.tools.council", "council_status"),
    "council_confirm": ("gods.tools.council", "council_confirm"),
    "council_action": ("gods.tools.council", "council_action"),
    "council_ledger": ("gods.tools.council", "council_ledger"),
    "council_resolutions": ("gods.tools.council", "council_resolutions"),
    "read": ("gods.tools.filesystem", "read"),
    "write_file": ("gods.tools.filesystem", "write_file"),
    "replace_content": ("gods.tools.filesystem", "replace_content"),
    "insert_content": ("gods.tools.filesystem", "insert_content"),
    "multi_replace": ("gods.tools.filesystem", "multi_replace"),
    "list": ("gods.tools.filesystem", "list"),
    "validate_path": ("gods.tools.filesystem", "validate_path"),
    "run_command": ("gods.tools.execution", "run_command"),
    "detach_list": ("gods.tools.detach", "detach_list"),
    "detach_stop": ("gods.tools.detach", "detach_stop"),
    "call_protocol": ("gods.tools.hermes", "call_protocol"),
    "route_protocol": ("gods.tools.hermes", "route_protocol"),
    "check_protocol_job": ("gods.tools.hermes", "check_protocol_job"),
    "register_contract": ("gods.tools.hermes", "register_contract"),
    "commit_contract": ("gods.tools.hermes", "commit_contract"),
    "list_contracts": ("gods.tools.hermes", "list_contracts"),
    "disable_contract": ("gods.tools.hermes", "disable_contract"),
    "reserve_port": ("gods.tools.hermes", "reserve_port"),
    "release_port": ("gods.tools.hermes", "release_port"),
    "list_port_leases": ("gods.tools.hermes", "list_port_leases"),
    "mnemo_write_agent": ("gods.tools.mnemosyne", "mnemo_write_agent"),
    "mnemo_list_agent": ("gods.tools.mnemosyne", "mnemo_list_agent"),
    "mnemo_read_agent": ("gods.tools.mnemosyne", "mnemo_read_agent"),
    "upload_artifact": ("gods.tools.mnemosyne", "upload_artifact"),
}

# Default agent toolset order.
_DEFAULT_TOOL_ORDER: list[str] = [
    "check_inbox",
    "check_outbox",
    "send_message",
    "finalize",
    "council_status",
    "council_confirm",
    "council_action",
    "council_ledger",
    "council_resolutions",
    "read",
    "write_file",
    "replace_content",
    "insert_content",
    "run_command",
    "detach_list",
    "detach_stop",
    "post_to_synod",
    "abstain_from_synod",
    "multi_replace",
    "list",
    "register_contract",
    "commit_contract",
    "list_contracts",
    "disable_contract",
    "reserve_port",
    "release_port",
    "list_port_leases",
    "mnemo_write_agent",
    "mnemo_list_agent",
    "mnemo_read_agent",
    "upload_artifact",
]

_CACHE: dict[str, object] = {}


def _load_tool(name: str):
    key = str(name)
    if key in _CACHE:
        return _CACHE[key]
    if key not in _TOOL_EXPORTS:
        raise AttributeError(f"module 'gods.tools' has no attribute '{key}'")
    module_name, attr_name = _TOOL_EXPORTS[key]
    mod = importlib.import_module(module_name)
    value = getattr(mod, attr_name)
    _CACHE[key] = value
    return value


class _LazyToolList:
    def _resolve(self) -> list:
        return [_load_tool(name) for name in _DEFAULT_TOOL_ORDER]

    def __iter__(self) -> Iterator:
        return iter(self._resolve())

    def __len__(self) -> int:
        return len(_DEFAULT_TOOL_ORDER)

    def __getitem__(self, idx):
        return self._resolve()[idx]

    def __repr__(self) -> str:
        return f"_LazyToolList(len={len(self)})"


GODS_TOOLS = _LazyToolList()


def available_tool_names() -> list[str]:
    return list(_DEFAULT_TOOL_ORDER)


def __getattr__(name: str):
    if name == "GODS_TOOLS":
        return GODS_TOOLS
    if name in _TOOL_EXPORTS:
        return _load_tool(name)
    raise AttributeError(f"module 'gods.tools' has no attribute '{name}'")


__all__ = [
    "GODS_TOOLS",
    "available_tool_names",
    "check_inbox",
    "check_outbox",
    "send_message",
    "finalize",
    "post_to_synod",
    "abstain_from_synod",
    "list_agents",
    "council_status",
    "council_confirm",
    "council_action",
    "council_ledger",
    "council_resolutions",
    "read",
    "write_file",
    "replace_content",
    "insert_content",
    "multi_replace",
    "list",
    "run_command",
    "detach_list",
    "detach_stop",
    "validate_path",
    "call_protocol",
    "route_protocol",
    "check_protocol_job",
    "register_contract",
    "commit_contract",
    "list_contracts",
    "disable_contract",
    "reserve_port",
    "release_port",
    "list_port_leases",
    "mnemo_write_agent",
    "mnemo_list_agent",
    "mnemo_read_agent",
    "upload_artifact",
]
