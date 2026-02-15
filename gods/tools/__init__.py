"""
Gods Tools Module
Unified export of all agent tools.
"""
from .communication import (
    check_inbox,
    send_message,
    send_to_human,
    finalize,
    post_to_synod,
    abstain_from_synod,
    record_protocol,
    list_agents,
)
from .filesystem import (
    read_file,
    write_file,
    replace_content,
    insert_content,
    multi_replace,
    list_dir,
    validate_path
)
from .execution import run_command
from .hermes import (
    register_protocol,
    call_protocol,  # exported for direct import, not in default agent toolset
    route_protocol,  # exported for direct import, not in default agent toolset
    check_protocol_job,  # exported for direct import, not in default agent toolset
    list_protocols,
    register_contract,
    commit_contract,
    resolve_contract,
    reserve_port,
    release_port,
    list_port_leases,
)

# Divine Toolset - Complete list for agent registration
GODS_TOOLS = [
    check_inbox,
    send_message,
    send_to_human,
    finalize,
    read_file,
    write_file,
    replace_content,
    insert_content,
    run_command,
    post_to_synod,
    abstain_from_synod,
    record_protocol,
    list_agents,
    multi_replace,
    list_dir,
    register_protocol,
    list_protocols,
    register_contract,
    commit_contract,
    resolve_contract,
    reserve_port,
    release_port,
    list_port_leases,
]

__all__ = [
    'GODS_TOOLS',
    'check_inbox',
    'send_message',
    'send_to_human',
    'finalize',
    'post_to_synod',
    'abstain_from_synod',
    'record_protocol',
    'list_agents',
    'read_file',
    'write_file',
    'replace_content',
    'insert_content',
    'multi_replace',
    'list_dir',
    'run_command',
    'validate_path',
    'register_protocol',
    'call_protocol',
    'route_protocol',
    'check_protocol_job',
    'list_protocols',
    'register_contract',
    'commit_contract',
    'resolve_contract',
    'reserve_port',
    'release_port',
    'list_port_leases',
]
