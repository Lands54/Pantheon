from gods.config import ProjectConfig, runtime_config
from gods.runtime.facade import DockerRuntimeManager, create_docker_args


def test_docker_manager_spec_and_mount_args():
    pid = "unit_docker_spec"
    aid = "ground"
    old = runtime_config.projects.get(pid)
    try:
        runtime_config.projects[pid] = ProjectConfig(
            command_executor="docker",
            docker_enabled=True,
            docker_image="gods-agent-base:py311",
            docker_network_mode="bridge_local_only",
            docker_cpu_limit=1.5,
            docker_memory_limit_mb=768,
            docker_extra_env={"X": "1"},
        )
        mgr = DockerRuntimeManager()
        spec = mgr.build_spec(pid, aid)
        assert spec.container_name.startswith("gods-")
        assert spec.image == "gods-agent-base:py311"

        args = create_docker_args(spec)
        joined = " ".join(args)
        assert "--cpus" in args
        assert "--memory" in args
        assert "/workspace/agent" in joined
        assert "/workspace/repo" in joined
        assert "PYTHONPATH=/workspace/repo" in joined
    finally:
        if old is None:
            runtime_config.projects.pop(pid, None)
        else:
            runtime_config.projects[pid] = old
