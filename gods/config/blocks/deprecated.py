from __future__ import annotations

from gods.config.declarations import ConfigBlockDecl, ConfigFieldDecl


CONFIG_BLOCKS: list[ConfigBlockDecl] = [
    ConfigBlockDecl(
        module_id="deprecated_project",
        module_title="Deprecated",
        scope="project",
        group_id="deprecated",
        group_title="Deprecated",
        default_collapsed=True,
        fields=[
            ConfigFieldDecl("autonomous_batch_size", "project", "integer", 4, False, "历史批量脉冲参数，当前保留为兼容阅读。", "project-runtime", [], status="deprecated"),
            ConfigFieldDecl("angelia_worker_per_agent", "project", "integer", 1, False, "历史 worker 配置，当前保留用于兼容读取。", "project-runtime", [], status="deprecated"),
            ConfigFieldDecl("summarize_threshold", "project", "integer", 12, False, "历史摘要阈值。", "project-runtime", [], status="deprecated"),
            ConfigFieldDecl("summarize_keep_count", "project", "integer", 5, False, "历史摘要保留条数。", "project-runtime", [], status="deprecated"),
            ConfigFieldDecl("docker_workspace_mount_mode", "project", "string", "agent_territory_rw", False, "历史 docker mount 模式。", "project-runtime", [], status="deprecated"),
            ConfigFieldDecl("hermes_enabled", "project", "boolean", True, False, "历史 Hermes 开关。", "project-runtime", [], status="deprecated"),
            ConfigFieldDecl("hermes_default_timeout_sec", "project", "integer", 30, False, "历史 Hermes 默认超时。", "project-runtime", [], status="deprecated"),
            ConfigFieldDecl("hermes_default_rate_per_minute", "project", "integer", 60, False, "历史 Hermes 默认速率。", "project-runtime", [], status="deprecated"),
            ConfigFieldDecl("hermes_default_max_concurrency", "project", "integer", 2, False, "历史 Hermes 默认并发。", "project-runtime", [], status="deprecated"),
        ],
    ),
]
