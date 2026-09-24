#!/usr/bin/env bash
if [ -n "${BASH_VERSION:-}" ]; then
  set -euo pipefail
else
  set -eu
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/scripts/.run"
LOG_DIR="$ROOT_DIR/scripts/logs"
INFRA_DIR="$ROOT_DIR/infrastructure"
COMPOSE_FILE="$INFRA_DIR/docker-compose.yml"

POSTGRES_CONTAINER="magic-postgres"
POSTGRES_PORT="${POSTGRES_PORT:-5434}"
REDIS_CONTAINER="magic-redis"
REDIS_PORT="${REDIS_PORT:-6379}"
DATABASE_URL=""
REDIS_URL=""

mkdir -p "$RUN_DIR" "$LOG_DIR"

# Detect venv activate path (Windows uses Scripts/, Unix uses bin/)
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]] || [[ "$(uname -s)" == MINGW* || "$(uname -s)" == MSYS* ]]; then
  VENV_BIN="Scripts"
else
  VENV_BIN="bin"
fi

# Use root .venv Python (3.11) instead of system Python (may be too new)
ROOT_PYTHON="$ROOT_DIR/.venv/$VENV_BIN/python"
if [[ ! -x "$ROOT_PYTHON" ]]; then
  ROOT_PYTHON="python"
fi

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  source "$ROOT_DIR/.env"
  set +a
fi

resolve_postgres_port() {
  # Reuse existing container port mapping when available.
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
  DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:${POSTGRES_PORT}/magic_sale"
}

resolve_redis_port() {
  # Reuse existing container port mapping when available.
  if docker ps -a --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
    local mapped_port
    mapped_port="$(
      docker inspect "$REDIS_CONTAINER" \
        --format '{{with index .HostConfig.PortBindings "6379/tcp"}}{{(index . 0).HostPort}}{{end}}' \
        2>/dev/null || true
    )"
    if [[ -n "$mapped_port" ]]; then
      REDIS_PORT="$mapped_port"
    fi
  fi
  REDIS_URL="redis://127.0.0.1:${REDIS_PORT}/0"
}

required_vars=(ZALO_BOT_TOKEN API_KEY BASE_URL MODEL_NAME)
for v in "${required_vars[@]}"; do
  if [[ -z "${!v:-}" ]]; then
    echo "Missing required variable in $ROOT_DIR/.env: $v"
    exit 1
  fi
done

ensure_venv() {
  local service="$1"
  local svc_dir="$ROOT_DIR/$service"
  local fresh="0"
  local need_install="0"
  local check_imports="import fastapi, uvicorn"

  if [[ "$service" == "mcp-service" ]]; then
    check_imports="import fastmcp"
  fi

  if [[ ! -d "$svc_dir/.venv" ]]; then
    echo "[setup] creating venv for $service"
    "$ROOT_PYTHON" -m venv "$svc_dir/.venv"
    fresh="1"
  fi

  # shellcheck disable=SC1091
  source "$svc_dir/.venv/$VENV_BIN/activate"
  if ! python - <<PY >/dev/null 2>&1
${check_imports}
PY
  then
    need_install="1"
  fi
  deactivate

  # Avoid reinstalling on every launch. Install only on first boot or broken env.
  if [[ "$fresh" == "1" || "$need_install" == "1" ]]; then
    echo "[setup] installing deps for $service"
    # shellcheck disable=SC1091
    source "$svc_dir/.venv/$VENV_BIN/activate"

    if [[ "$service" == "prompt-service" ]]; then
      # prompt-service pins asyncpg==0.29.0, which fails to build on Python 3.13.
      local tmp_req
      tmp_req="$(mktemp)"
      grep -v '^asyncpg==' "$svc_dir/requirements.txt" > "$tmp_req"
      pip install -q -r "$tmp_req"
      pip install -q 'asyncpg>=0.30,<0.31'
      rm -f "$tmp_req"
    else
      pip install -q -r "$svc_dir/requirements.txt"
    fi
    deactivate
  fi
}

start_postgres() {
  # If another Postgres is already listening on the target port, reuse it.
  if pg_isready -h 127.0.0.1 -p "$POSTGRES_PORT" -U postgres -d magic_sale >/dev/null 2>&1; then
    echo "[db] using existing postgres on 127.0.0.1:${POSTGRES_PORT}"
    return
  fi

  if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "[db] missing compose file: $COMPOSE_FILE"
    exit 1
  fi

  echo "[db] ensuring postgres via docker compose"
  (
    cd "$INFRA_DIR"
    docker compose up -d postgres >/dev/null
  )

  echo "[db] waiting for postgres ready"
  for _ in {1..30}; do
    if docker exec "$POSTGRES_CONTAINER" pg_isready -U postgres -d magic_sale >/dev/null 2>&1; then
      echo "[db] postgres ready"
      return
    fi
    sleep 1
  done
  echo "[db] postgres did not become ready in time"
  exit 1
}

start_redis() {
  # If Redis is already running and reachable, reuse it.
  if docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$" && \
     docker exec "$REDIS_CONTAINER" redis-cli ping >/dev/null 2>&1; then
    echo "[cache] using existing redis on 127.0.0.1:${REDIS_PORT}"
    return
  fi

  if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "[cache] missing compose file: $COMPOSE_FILE"
    exit 1
  fi

  echo "[cache] ensuring redis via docker compose"
  (
    cd "$INFRA_DIR"
    docker compose up -d redis >/dev/null
  )

  echo "[cache] waiting for redis ready"
  for _ in {1..30}; do
    if docker exec "$REDIS_CONTAINER" redis-cli ping >/dev/null 2>&1; then
      echo "[cache] redis ready"
      return
    fi
    sleep 1
  done
  echo "[cache] redis did not become ready in time"
  exit 1
}

restart_service() {
  local name="$1"
  local cmd="$2"
  local pid_file="$RUN_DIR/${name}.pid"
  local log_file="$LOG_DIR/${name}.log"

  if [[ -f "$pid_file" ]]; then
    local old_pid
    old_pid="$(cat "$pid_file")"

    if kill -0 "$old_pid" 2>/dev/null; then
      echo "[run] restarting $name (pid $old_pid)"
      kill "$old_pid" || true
      for _ in {1..20}; do
        if ! kill -0 "$old_pid" 2>/dev/null; then
          break
        fi
        sleep 0.2
      done
      if kill -0 "$old_pid" 2>/dev/null; then
        kill -9 "$old_pid" || true
      fi
    else
      echo "[run] removing stale pid for $name"
    fi

    rm -f "$pid_file"
  else
    echo "[run] starting $name"
  fi

  nohup bash -lc "$cmd" >"$log_file" 2>&1 &
  echo $! >"$pid_file"
}

ensure_venv "prompt-service"
ensure_venv "models-service"
ensure_venv "order-service"
ensure_venv "mcp-service"
ensure_venv "zalo-service"
ensure_venv "rag-service"
ensure_venv "chat-service"

resolve_postgres_port
resolve_redis_port
start_postgres
start_redis

echo "[db] running prompt migration"
(
  cd "$ROOT_DIR/prompt-service"
  # shellcheck disable=SC1091
  source .venv/$VENV_BIN/activate
  export DATABASE_URL="$DATABASE_URL"
  PYTHONPATH=. alembic upgrade head
  deactivate
)

echo "[db] running order migration"
(
  cd "$ROOT_DIR/order-service"
  # shellcheck disable=SC1091
  source .venv/$VENV_BIN/activate
  export DATABASE_URL="$DATABASE_URL"
  PYTHONPATH=. alembic upgrade head
  deactivate
)

echo "[db] running chat migration"
(
  cd "$ROOT_DIR/chat-service"
  # shellcheck disable=SC1091
  source .venv/$VENV_BIN/activate
  export DATABASE_URL="$DATABASE_URL"
  PYTHONPATH=. alembic upgrade head
  deactivate
)

restart_service "prompt-service" \
  "cd '$ROOT_DIR/prompt-service' && source .venv/$VENV_BIN/activate && export DATABASE_URL='$DATABASE_URL' && exec python -m uvicorn main:app --host 127.0.0.1 --port 8001"

restart_service "chat-service" \
  "cd '$ROOT_DIR/chat-service' && source .venv/$VENV_BIN/activate && export DATABASE_URL='$DATABASE_URL' REDIS_URL='$REDIS_URL' && exec python -m uvicorn main:app --host 127.0.0.1 --port 8007"

restart_service "models-service" \
  "cd '$ROOT_DIR/models-service' && source .venv/$VENV_BIN/activate && export PYTHONUTF8=1 PYTHONIOENCODING=utf-8 MODEL_NAME='${MODEL_NAME}' API_KEY='${API_KEY}' BASE_URL='${BASE_URL}' PROMPT_SERVICE_URL='http://127.0.0.1:8001' MCP_SERVICE_URL='http://127.0.0.1:8004' CHAT_SERVICE_URL='http://127.0.0.1:8007' && exec python -m uvicorn main:app --host 127.0.0.1 --port 8000"

restart_service "order-service" \
  "cd '$ROOT_DIR/order-service' && source .venv/$VENV_BIN/activate && export DATABASE_URL='$DATABASE_URL' SMTP_HOST='${SMTP_HOST:-smtp.gmail.com}' SMTP_PORT='${SMTP_PORT:-587}' SMTP_USER='${SMTP_USER}' SMTP_PASSWORD='${SMTP_PASSWORD}' SMTP_FROM_NAME='${SMTP_FROM_NAME:-Nhà Sữa}' SMTP_FROM_EMAIL='${SMTP_FROM_EMAIL}' EMAIL_ENABLED='${EMAIL_ENABLED:-false}' SEPAY_API_KEY='${SEPAY_API_KEY}' ZALO_SERVICE_URL='http://127.0.0.1:8080' && exec python -m uvicorn main:app --host 127.0.0.1 --port 8003"

restart_service "mcp-service" \
  "cd '$ROOT_DIR/mcp-service' && source .venv/$VENV_BIN/activate && export DATABASE_URL='$DATABASE_URL' PROMPT_SERVICE_URL='http://127.0.0.1:8001' ORDER_SERVICE_URL='http://127.0.0.1:8003' MCP_TRANSPORT='http' SMTP_HOST='${SMTP_HOST:-smtp.gmail.com}' SMTP_PORT='${SMTP_PORT:-587}' SMTP_USER='${SMTP_USER}' SMTP_PASSWORD='${SMTP_PASSWORD}' SMTP_FROM_NAME='${SMTP_FROM_NAME:-Nhà Sữa}' SMTP_FROM_EMAIL='${SMTP_FROM_EMAIL}' EMAIL_ENABLED='${EMAIL_ENABLED:-false}' BANK_BIN='${BANK_BIN:-970422}' BANK_ACCOUNT_NO='${BANK_ACCOUNT_NO}' BANK_ACCOUNT_NAME='${BANK_ACCOUNT_NAME}' ZALO_SERVICE_URL='http://127.0.0.1:8080' && exec python main.py"

restart_service "zalo-service" \
  "cd '$ROOT_DIR/zalo-service' && source .venv/$VENV_BIN/activate && export ZALO_BOT_TOKEN='${ZALO_BOT_TOKEN}' ZALO_BASE_URL='${ZALO_BASE_URL:-https://bot-api.zaloplatforms.com}' MODEL_SERVICE_URL='http://127.0.0.1:8000' WEBHOOK_SECRET_TOKEN='${WEBHOOK_SECRET_TOKEN:-}' LOG_LEVEL='${LOG_LEVEL:-INFO}' TRACE_CHAT_CONTENT='${TRACE_CHAT_CONTENT:-0}' && exec python main.py --mode polling"

restart_service "rag-service" \
  "cd '$ROOT_DIR/rag-service' && source .venv/$VENV_BIN/activate && export GEMINI_API_KEY='${GEMINI_API_KEY:-}' QDRANT_HOST='127.0.0.1' QDRANT_PORT='6333' TEI_RERANKER_URL='http://127.0.0.1:8005' && exec python -m uvicorn main:app --host 127.0.0.1 --port 8006"

echo "[check] waiting services"
all_ok="0"
for _ in {1..20}; do
  mcp_code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8004/mcp || true)"
  if curl -sf http://127.0.0.1:8001/health >/dev/null 2>&1 && \
     curl -sf http://127.0.0.1:8007/health >/dev/null 2>&1 && \
     curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 && \
     curl -sf http://127.0.0.1:8003/health >/dev/null 2>&1 && \
     [[ "$mcp_code" == "200" || "$mcp_code" == "202" || "$mcp_code" == "406" ]]; then
    all_ok="1"
    break
  fi
  sleep 1
done

if [[ "$all_ok" != "1" ]]; then
  echo "[error] one or more services failed health checks"
  echo "prompt-service health: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8001/health || echo fail)"
  echo "chat-service health: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8007/health || echo fail)"
  echo "models-service health: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health || echo fail)"
  echo "order-service health: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8003/health || echo fail)"
  echo "mcp-service health: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8004/mcp || echo fail)"
  echo
  echo "[logs] tail prompt-service"
  tail -n 80 "$LOG_DIR/prompt-service.log" || true
  echo
  echo "[logs] tail chat-service"
  tail -n 80 "$LOG_DIR/chat-service.log" || true
  exit 1
fi

echo
echo "✅ Chat stack is up!"
echo
echo "Core services:"
echo "  prompt-service:  http://127.0.0.1:8001/health"
echo "  chat-service:    http://127.0.0.1:8007/health  (NEW - conversation history)"
echo "  models-service:  http://127.0.0.1:8000/health"
echo "  order-service:   http://127.0.0.1:8003/health"
echo "  mcp-service:     http://127.0.0.1:8004/mcp"
echo
echo "Optional services:"
echo "  rag-service:     http://127.0.0.1:8006/api/v1/health"
echo "  zalo-service:    polling mode (reads messages directly from Zalo OA API)"
echo
echo "Infrastructure:"
echo "  PostgreSQL:      127.0.0.1:${POSTGRES_PORT}"
echo "  Redis:           127.0.0.1:${REDIS_PORT}"
echo
echo "Note: RAG service requires Qdrant (port 6333) and TEI reranker (port 8005)"
echo "      Start them with: cd rag-service && docker-compose up -d qdrant tei-reranker"
echo
echo "Useful commands:"
echo "  scripts/chat-status.sh   - Check service status"
echo "  scripts/chat-logs.sh     - View logs"
echo "  scripts/chat-down.sh     - Stop all services"
