from __future__ import annotations

from gods.config.declarations import ConfigBlockDecl, ConfigFieldDecl


CONFIG_BLOCKS: list[ConfigBlockDecl] = [
    ConfigBlockDecl(
        module_id="system",
        module_title="System",
        scope="system",
        group_id="system",
        group_title="System",
        fields=[
            ConfigFieldDecl(
                key="openrouter_api_key",
                scope="system",
                type="string",
                default="",
                nullable=False,
                description="OpenRouter API Key。保存时会脱敏回显。",
                owner="core-runtime",
                runtime_used_by=["gods/agents/brain.py", "api/services/config_service.py"],
            ),
            ConfigFieldDecl(
                key="current_project",
                scope="system",
                type="string",
                default="default",
                nullable=False,
                description="当前激活项目 ID。",
                owner="core-runtime",
                runtime_used_by=["gods/config/runtime.py", "api/services/project_service.py"],
            ),
            ConfigFieldDecl(
                key="projects",
                scope="system",
                type="object",
                default={"default": {"name": "Default World"}},
                nullable=False,
                description="项目配置映射。",
                owner="core-runtime",
                runtime_used_by=["gods/config/runtime.py", "gods/config/loader.py"],
            ),
        ],
    )
]
