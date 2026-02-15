# gods-agent-base

Build:

```bash
docker build -t gods-agent-base:py311 docker/agent-base
```

This image is used by project runtime with long-lived per-agent containers.

Default behavior:
- Workdir: `/workspace`
- Agent territory mount: `/workspace/agent` (rw)
- Repo mount: `/workspace/repo` (ro)
- `PYTHONPATH=/workspace/repo` is injected during `docker exec`
