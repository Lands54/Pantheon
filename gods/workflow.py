"""
Backward-compatible wrapper.
Legacy workflow implementation moved to gods.legacy.workflow.
"""

from gods.legacy.workflow import (  # noqa: F401
    should_continue,
    summarize_conversation,
    create_gods_workflow,
    create_private_workflow,
)
