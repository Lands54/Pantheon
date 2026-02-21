from __future__ import annotations

from gods.config.declarations import ConfigBlockDecl, ConfigFieldDecl


CONFIG_BLOCKS: list[ConfigBlockDecl] = [
    ConfigBlockDecl(
        module_id="angelia",
        module_title="Angelia",
        scope="project",
        group_id="angelia",
        group_title="Angelia",
        fields=[
            ConfigFieldDecl("angelia_enabled", "project", "boolean", True, False, "是否启用 Angelia 事件驱动。", "project-runtime", ["gods/angelia/scheduler.py"]),
            ConfigFieldDecl("angelia_event_max_attempts", "project", "integer", 3, False, "事件最大重试次数。", "project-runtime", ["gods/angelia/policy.py"]),
            ConfigFieldDecl("angelia_processing_timeout_sec", "project", "integer", 60, False, "单事件处理超时（秒）。", "project-runtime", ["gods/angelia/policy.py"]),
            ConfigFieldDecl("angelia_pick_batch_size", "project", "integer", 10, False, "单个 worker 一次从队列拉取的最大事件数。", "project-runtime", ["gods/angelia/policy.py", "gods/angelia/worker.py"], constraints={"min": 1, "max": 100}),
            ConfigFieldDecl("angelia_cooldown_preempt_types", "project", "array", ["mail_event", "manual", "detach_failed_event", "detach_lost_event"], False, "冷却期间可抢占事件类型。", "project-runtime", ["gods/angelia/policy.py"]),
            ConfigFieldDecl("angelia_timer_enabled", "project", "boolean", True, False, "是否启用 idle timer 脉冲。", "project-runtime", ["gods/angelia/policy.py"]),
            ConfigFieldDecl("angelia_timer_idle_sec", "project", "integer", 60, False, "idle timer 秒数。", "project-runtime", ["gods/angelia/policy.py", "gods/angelia/pulse/policy.py"]),
            ConfigFieldDecl("angelia_dedupe_window_sec", "project", "integer", 5, False, "事件去重窗口（秒）。", "project-runtime", ["gods/angelia/policy.py"]),
        ],
    ),
]
