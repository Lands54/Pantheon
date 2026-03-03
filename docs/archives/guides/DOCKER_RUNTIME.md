# Docker Runtime (Phase-1)

## Scope

Phase-1 containerizes only `run_command` execution:

- Agent reasoning loop remains on host process.
- Each active agent can map to one long-lived docker container.

## Build base image

```bash
docker build -t gods-agent-base:py311 docker/agent-base
```

## Runtime model

- Container name: `gods-{project_id}-{agent_id}`
- Host agent territory: `projects/{project_id}/agents/{agent_id}`
- Container territory mount: `/workspace/agent` (rw)
- Host repo mount: project root -> `/workspace/repo` (ro)
- Exec env: `PYTHONPATH=/workspace/repo`

## Config keys

Project config supports:

- `command_executor`: `docker|local`
- `docker_enabled`
- `docker_image`
- `docker_network_mode`
- `docker_auto_start_on_project_start`
- `docker_auto_stop_on_project_stop`
- `docker_workspace_mount_mode`
- `docker_readonly_rootfs`
- `docker_extra_env`
- `docker_cpu_limit`
- `docker_memory_limit_mb`

## API

- `GET /projects/{project_id}/runtime/agents`
- `POST /projects/{project_id}/runtime/agents/{agent_id}/restart`
- `POST /projects/{project_id}/runtime/reconcile`

## CLI

- `./temple.sh runtime status -p <project>`
- `./temple.sh runtime restart <agent> -p <project>`
- `./temple.sh runtime reconcile -p <project>`

## Backend Switch

Set:

```bash
./temple.sh -p <project> config set command_executor local
```

This switches execution to host `subprocess` backend.
