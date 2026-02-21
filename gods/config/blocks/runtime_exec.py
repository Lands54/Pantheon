from __future__ import annotations

from gods.config.declarations import ConfigBlockDecl, ConfigFieldDecl


CONFIG_BLOCKS: list[ConfigBlockDecl] = [
    ConfigBlockDecl(
        module_id="runtime_exec",
        module_title="Runtime Exec",
        scope="project",
        group_id="runtime",
        group_title="Runtime",
        fields=[
            ConfigFieldDecl("command_executor", "project", "string", "docker", False, "命令执行后端。", "project-runtime", ["api/services/project_service.py"], enum=["docker", "local"]),
            ConfigFieldDecl("command_max_parallel", "project", "integer", 2, False, "命令并行上限。", "project-runtime", ["gods/tools/execution.py"]),
            ConfigFieldDecl("command_timeout_sec", "project", "integer", 60, False, "命令超时（秒）。", "project-runtime", ["gods/tools/execution.py"]),
            ConfigFieldDecl("command_max_memory_mb", "project", "integer", 512, False, "命令内存上限（MB）。", "project-runtime", ["gods/tools/execution.py"]),
            ConfigFieldDecl("command_max_cpu_sec", "project", "integer", 15, False, "命令 CPU 时间上限（秒）。", "project-runtime", ["gods/tools/execution.py"]),
            ConfigFieldDecl("command_max_output_chars", "project", "integer", 4000, False, "命令输出字符上限。", "project-runtime", ["gods/tools/execution.py"]),
            ConfigFieldDecl("docker_enabled", "project", "boolean", True, False, "是否启用 docker runtime。", "project-runtime", ["api/services/project_service.py", "api/services/simulation_service.py"]),
            ConfigFieldDecl("docker_image", "project", "string", "gods-agent-base:py311", False, "docker 镜像名。", "project-runtime", ["gods/runtime/docker/manager.py"]),
            ConfigFieldDecl("docker_network_mode", "project", "string", "bridge_local_only", False, "docker 网络模式。", "project-runtime", ["gods/runtime/docker/manager.py"], enum=["bridge_local_only", "none"]),
            ConfigFieldDecl("docker_auto_start_on_project_start", "project", "boolean", True, False, "项目启动时自动启动 runtime。", "project-runtime", ["api/services/project_service.py"]),
            ConfigFieldDecl("docker_auto_stop_on_project_stop", "project", "boolean", True, False, "项目停止时自动停止 runtime。", "project-runtime", ["api/services/project_service.py"]),
            ConfigFieldDecl("docker_readonly_rootfs", "project", "boolean", False, False, "容器 rootfs 只读。", "project-runtime", ["gods/runtime/docker/manager.py"]),
            ConfigFieldDecl("docker_extra_env", "project", "object", {}, False, "容器额外环境变量。", "project-runtime", ["gods/runtime/docker/manager.py"]),
            ConfigFieldDecl("docker_cpu_limit", "project", "number", 1.0, False, "容器 CPU 限额。", "project-runtime", ["gods/runtime/docker/manager.py"]),
            ConfigFieldDecl("docker_memory_limit_mb", "project", "integer", 512, False, "容器内存限额（MB）。", "project-runtime", ["gods/runtime/docker/manager.py"]),
            ConfigFieldDecl("detach_enabled", "project", "boolean", True, False, "是否启用 detach 任务。", "project-runtime", ["gods/runtime/detach/service.py"]),
            ConfigFieldDecl("detach_max_running_per_agent", "project", "integer", 2, False, "单 agent dettach 运行上限。", "project-runtime", ["gods/runtime/detach/service.py"]),
            ConfigFieldDecl("detach_max_running_per_project", "project", "integer", 8, False, "项目 detach 运行上限。", "project-runtime", ["gods/runtime/detach/service.py"]),
            ConfigFieldDecl("detach_queue_max_per_agent", "project", "integer", 8, False, "单 agent detach 队列上限。", "project-runtime", ["gods/runtime/detach/service.py"]),
            ConfigFieldDecl("detach_ttl_sec", "project", "integer", 1800, False, "detach 任务 TTL（秒）。", "project-runtime", ["gods/runtime/detach/service.py"]),
            ConfigFieldDecl("detach_stop_grace_sec", "project", "integer", 10, False, "detach 停止宽限（秒）。", "project-runtime", ["gods/runtime/detach/service.py"]),
            ConfigFieldDecl("detach_log_tail_chars", "project", "integer", 4000, False, "detach 日志尾部字符上限。", "project-runtime", ["gods/runtime/detach/service.py"]),
        ],
    ),
]
