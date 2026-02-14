"""
Gods Tools Module
Unified export of all agent tools.
"""
from .communication import (
    check_inbox,
    send_message,
    send_to_human,
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

# Divine Toolset - Complete list for agent registration
GODS_TOOLS = [
    check_inbox,
    send_message,
    send_to_human,
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
    list_dir
]

__all__ = [
    'GODS_TOOLS',
    'check_inbox',
    'send_message',
    'send_to_human',
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
    'validate_path'
]
