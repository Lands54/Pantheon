from __future__ import annotations

from gods.config.declarations import ConfigBlockDecl, ConfigFieldDecl


CONFIG_BLOCKS: list[ConfigBlockDecl] = [
    ConfigBlockDecl(
        module_id="memory",
        module_title="Memory",
        scope="project",
        group_id="memory",
        group_title="Memory",
        fields=[
            ConfigFieldDecl("memory_compact_trigger_tokens", "project", "integer", 12000, False, "触发记忆压缩的 token 阈值。", "project-runtime", ["gods/mnemosyne/compaction.py"]),
            ConfigFieldDecl("memory_compact_strategy", "project", "string", "semantic_llm", False, "记忆压缩策略。", "project-runtime", ["gods/mnemosyne/compaction.py"], enum=["semantic_llm", "rule_based"]),
        ],
    ),
    ConfigBlockDecl(
        module_id="context",
        module_title="Context",
        scope="project",
        group_id="context",
        group_title="Context",
        fields=[
            ConfigFieldDecl("context_strategy", "project", "string", "sequential_v1", False, "上下文构建策略。", "project-runtime", ["gods/janus/context_policy.py"], enum=["sequential_v1"]),
            ConfigFieldDecl("context_token_budget_total", "project", "integer", 32000, False, "总上下文 token 预算。", "project-runtime", ["gods/janus/context_policy.py"], constraints={"min": 4000, "max": 256000}),
            ConfigFieldDecl("context_budget_task_state", "project", "integer", 4000, False, "任务状态区块预算。", "project-runtime", ["gods/janus/context_policy.py"]),
            ConfigFieldDecl("context_budget_inbox", "project", "integer", 4000, False, "mailbox 区块总预算。", "project-runtime", ["gods/janus/context_policy.py"]),
            ConfigFieldDecl("context_budget_inbox_unread", "project", "integer", 2000, False, "未读 inbox 预算。", "project-runtime", ["gods/janus/context_policy.py"]),
            ConfigFieldDecl("context_budget_inbox_read_recent", "project", "integer", 1000, False, "已读近期 inbox 预算。", "project-runtime", ["gods/janus/context_policy.py"]),
            ConfigFieldDecl("context_budget_inbox_receipts", "project", "integer", 1000, False, "发件回执预算。", "project-runtime", ["gods/janus/context_policy.py"]),
            ConfigFieldDecl("context_short_window_intents", "project", "integer", 120, False, "短窗 intent 数量。", "project-runtime", ["gods/janus/context_policy.py", "gods/mnemosyne/janus_snapshot.py"]),
            ConfigFieldDecl("context_n_recent", "project", "integer", 12, False, "recent 卡片数量。", "project-runtime", ["gods/janus/context_policy.py", "gods/janus/strategies/sequential_v1.py"], constraints={"min": 1, "max": 5000}),
            ConfigFieldDecl("context_recent_token_budget", "project", "integer", 6000, False, "recent 区块 token 预算。", "project-runtime", ["gods/janus/context_policy.py", "gods/janus/strategies/sequential_v1.py"], constraints={"min": 0, "max": 256000}),
            ConfigFieldDecl("context_token_budget_chronicle_trigger", "project", "integer", 8000, False, "chronicle 触发压缩预算阈值。", "project-runtime", ["gods/janus/context_policy.py", "gods/janus/strategies/sequential_v1.py"], constraints={"min": 1000, "max": 512000}),
            ConfigFieldDecl("context_include_inbox_status_hints", "project", "boolean", True, False, "是否注入 inbox 状态提示。", "project-runtime", ["gods/janus/context_policy.py"]),
            ConfigFieldDecl("context_write_build_report", "project", "boolean", True, False, "是否写入上下文构建报告。", "project-runtime", ["gods/janus/context_policy.py"]),
            ConfigFieldDecl("metis_refresh_mode", "project", "string", "pulse", False, "Metis envelope 刷新模式。", "project-runtime", ["gods/metis/snapshot.py", "gods/metis/strategy_runtime.py"], enum=["pulse", "node"]),
        ],
    ),
]
