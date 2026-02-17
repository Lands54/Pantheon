#!/usr/bin/env bash
set -euo pipefail

# Stop Gods API server from repository root.
# Priority:
# 1) PID file: /tmp/gods_server.pid (or GODS_SERVER_PID override)
# 2) Process listening on tcp:8000
# 3) Process command matching "python server.py" or "uvicorn api.app:app"

SERVER_PID_FILE="${GODS_SERVER_PID:-/tmp/gods_server.pid}"
PORT="${GODS_SERVER_PORT:-8000}"
STOPPED=0

stop_pid() {
  local pid="$1"
  if [[ -z "${pid}" ]]; then
    return 0
  fi
  if ! kill -0 "${pid}" 2>/dev/null; then
    return 0
  fi

  echo "Stopping PID ${pid}..."
  kill "${pid}" 2>/dev/null || true
  for _ in $(seq 1 20); do
    if ! kill -0 "${pid}" 2>/dev/null; then
      STOPPED=1
      return 0
    fi
    sleep 0.2
  done

  echo "PID ${pid} still alive, force killing..."
  kill -9 "${pid}" 2>/dev/null || true
  STOPPED=1
}

if [[ -f "${SERVER_PID_FILE}" ]]; then
  PID_FROM_FILE="$(cat "${SERVER_PID_FILE}" || true)"
  stop_pid "${PID_FROM_FILE}"
  rm -f "${SERVER_PID_FILE}"
fi

if command -v lsof >/dev/null 2>&1; then
  PORT_PIDS="$(lsof -ti "tcp:${PORT}" || true)"
  if [[ -n "${PORT_PIDS}" ]]; then
    for pid in ${PORT_PIDS}; do
      stop_pid "${pid}"
    done
  fi
fi

PATTERN_PIDS="$(pgrep -f 'python server.py|uvicorn api.app:app' || true)"
if [[ -n "${PATTERN_PIDS}" ]]; then
  for pid in ${PATTERN_PIDS}; do
    stop_pid "${pid}"
  done
fi

if [[ "${STOPPED}" -eq 1 ]]; then
  echo "Gods API server stopped."
else
  echo "No running Gods API server process found."
fi

