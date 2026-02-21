from __future__ import annotations

from gods.config.declarations import ConfigBlockDecl, ConfigFieldDecl


CONFIG_BLOCKS: list[ConfigBlockDecl] = [
    ConfigBlockDecl(
        module_id="runtime_llm",
        module_title="Runtime LLM",
        scope="project",
        group_id="runtime",
        group_title="Runtime",
        fields=[
            ConfigFieldDecl("llm_control_enabled", "project", "boolean", True, False, "启用 LLM 全局/项目限流控制。", "project-runtime", ["gods/agents/llm_control.py", "gods/agents/brain.py"]),
            ConfigFieldDecl("llm_global_max_concurrency", "project", "integer", 8, False, "LLM 全局并发上限。", "project-runtime", ["gods/agents/llm_control.py"], constraints={"min": 1, "max": 256}),
            ConfigFieldDecl("llm_global_rate_per_minute", "project", "integer", 120, False, "LLM 全局 RPM 上限。", "project-runtime", ["gods/agents/llm_control.py"], constraints={"min": 1, "max": 200000}),
            ConfigFieldDecl("llm_project_max_concurrency", "project", "integer", 4, False, "LLM 项目并发上限。", "project-runtime", ["gods/agents/llm_control.py"], constraints={"min": 1, "max": 256}),
            ConfigFieldDecl("llm_project_rate_per_minute", "project", "integer", 60, False, "LLM 项目 RPM 上限。", "project-runtime", ["gods/agents/llm_control.py"], constraints={"min": 1, "max": 200000}),
            ConfigFieldDecl("llm_acquire_timeout_sec", "project", "integer", 20, False, "限流许可等待超时（秒）。", "project-runtime", ["gods/agents/llm_control.py"], constraints={"min": 1, "max": 300}),
            ConfigFieldDecl("llm_request_timeout_sec", "project", "integer", 90, False, "单次 LLM 请求超时（秒）。", "project-runtime", ["gods/agents/brain.py"], constraints={"min": 1, "max": 600}),
            ConfigFieldDecl("llm_retry_interval_ms", "project", "integer", 100, False, "限流重试间隔（毫秒）。", "project-runtime", ["gods/agents/llm_control.py"], constraints={"min": 10, "max": 5000}),
        ],
    ),
]
