from __future__ import annotations

from gods.config.declarations import ConfigBlockDecl, ConfigFieldDecl


CONFIG_BLOCKS: list[ConfigBlockDecl] = [
    ConfigBlockDecl(
        module_id="debug",
        module_title="Debug",
        scope="project",
        group_id="debug",
        group_title="Debug",
        fields=[
            ConfigFieldDecl("debug_trace_enabled", "project", "boolean", True, False, "是否启用调试 trace。", "project-runtime", ["gods/agents/debug_trace.py"]),
            ConfigFieldDecl("debug_trace_max_events", "project", "integer", 200, False, "单 pulse 最大 trace 事件数。", "project-runtime", ["gods/agents/debug_trace.py"]),
            ConfigFieldDecl("debug_trace_full_content", "project", "boolean", True, False, "是否保存完整 trace 内容。", "project-runtime", ["gods/agents/debug_trace.py"]),
            ConfigFieldDecl("debug_llm_trace_enabled", "project", "boolean", True, False, "是否启用 LLM IO trace。", "project-runtime", ["gods/agents/brain.py"]),
        ],
    ),
]
