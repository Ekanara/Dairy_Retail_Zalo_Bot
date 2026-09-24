#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/scripts/.run"
POSTGRES_CONTAINER="magic-postgres"
REDIS_CONTAINER="magic-redis"

stop_pid() {
  local name="$1"
  local pid_file="$RUN_DIR/${name}.pid"

  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "[stop] $name (pid $pid)"
      kill "$pid" || true
    fi
    rm -f "$pid_file"
  fi
}

stop_pid "zalo-service"
stop_pid "rag-service"
stop_pid "mcp-service"
stop_pid "order-service"
stop_pid "models-service"
stop_pid "chat-service"
stop_pid "prompt-service"

if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
  echo "[stop] postgres container"
  docker stop "$POSTGRES_CONTAINER" >/dev/null || true
fi

if docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
  echo "[stop] redis container"
  docker stop "$REDIS_CONTAINER" >/dev/null || true
fi

echo "✅ Chat stack stopped."
