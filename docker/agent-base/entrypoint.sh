#!/usr/bin/env sh
set -eu

mkdir -p /workspace/agent || true
mkdir -p /workspace/.cache || true

# Keep container alive for docker exec runtime commands.
exec tail -f /dev/null
