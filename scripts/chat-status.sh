#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/scripts/.run"
POSTGRES_CONTAINER="magic-postgres"
POSTGRES_PORT="${POSTGRES_PORT:-5434}"
REDIS_CONTAINER="magic-redis"
REDIS_PORT="${REDIS_PORT:-6379}"

resolve_postgres_port() {
  if docker ps -a --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
    local mapped_port
    mapped_port="$(
      docker inspect "$POSTGRES_CONTAINER" \
        --format '{{with index .HostConfig.PortBindings "5432/tcp"}}{{(index . 0).HostPort}}{{end}}' \
        2>/dev/null || true
    )"
    if [[ -n "$mapped_port" ]]; then
      POSTGRES_PORT="$mapped_port"
    fi
  fi
}

show_proc() {
  local name="$1"
  local pid_file="$RUN_DIR/${name}.pid"
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "  ✅ $name (pid $(cat "$pid_file"))"
  else
    echo "  ❌ $name"
  fi
}

echo "Process status:"
show_proc "prompt-service"
show_proc "chat-service"
show_proc "models-service"
show_proc "order-service"
show_proc "mcp-service"
show_proc "rag-service"
show_proc "zalo-service"

echo
echo "HTTP health:"
curl -sf http://127.0.0.1:8001/health >/dev/null 2>&1 && echo "  ✅ prompt-service :8001" || echo "  ❌ prompt-service :8001"
curl -sf http://127.0.0.1:8007/health >/dev/null 2>&1 && echo "  ✅ chat-service :8007" || echo "  ❌ chat-service :8007"
curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 && echo "  ✅ models-service :8000" || echo "  ❌ models-service :8000"
curl -sf http://127.0.0.1:8003/health >/dev/null 2>&1 && echo "  ✅ order-service :8003" || echo "  ❌ order-service :8003"
mcp_code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8004/mcp || true)"
if [[ "$mcp_code" == "200" || "$mcp_code" == "202" || "$mcp_code" == "406" ]]; then
  echo "  ✅ mcp-service :8004"
else
  echo "  ❌ mcp-service :8004"
fi
curl -sf http://127.0.0.1:8006/api/v1/health >/dev/null 2>&1 && echo "  ✅ rag-service :8006" || echo "  ❌ rag-service :8006"

echo
echo "Infrastructure:"
resolve_postgres_port
if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
  echo "  ✅ PostgreSQL (${POSTGRES_CONTAINER}) on 127.0.0.1:${POSTGRES_PORT}"
elif pg_isready -h 127.0.0.1 -p "$POSTGRES_PORT" -U postgres -d magic_sale >/dev/null 2>&1; then
  echo "  ✅ PostgreSQL (external) on 127.0.0.1:${POSTGRES_PORT}"
else
  echo "  ❌ PostgreSQL stopped"
fi

if docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
  echo "  ✅ Redis (${REDIS_CONTAINER}) on 127.0.0.1:${REDIS_PORT}"
else
  echo "  ❌ Redis stopped"
fi
