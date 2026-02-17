from gods.config import ProjectConfig, runtime_config
from gods.runtime.facade import DockerBackend, LocalSubprocessBackend, resolve_execution_backend


def test_execution_backend_resolver_docker_and_local():
    pid = "unit_backend_resolver"
    old = runtime_config.projects.get(pid)
    try:
        runtime_config.projects[pid] = ProjectConfig(command_executor="docker", docker_enabled=True)
        b1 = resolve_execution_backend(pid)
        assert isinstance(b1, DockerBackend)

        runtime_config.projects[pid].docker_enabled = False
        b2 = resolve_execution_backend(pid)
        assert isinstance(b2, LocalSubprocessBackend)

        runtime_config.projects[pid].docker_enabled = True
        runtime_config.projects[pid].command_executor = "local"
        b3 = resolve_execution_backend(pid)
        assert isinstance(b3, LocalSubprocessBackend)
    finally:
        if old is None:
            runtime_config.projects.pop(pid, None)
        else:
            runtime_config.projects[pid] = old
