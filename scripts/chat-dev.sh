#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POSTGRES_CONTAINER="magic-sale-postgres-chat"
POSTGRES_PORT="${POSTGRES_PORT:-55432}"
DATABASE_URL=""
POSTGRES_IMAGE="${POSTGRES_IMAGE:-pgvector/pgvector:pg16}"
POSTGRES_VOLUME="${POSTGRES_VOLUME:-magic_sale_postgres_chat_data}"
POSTGRES_INIT_SQL="$ROOT_DIR/infrastructure/postgres/init.sql"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  source "$ROOT_DIR/.env"
  set +a
fi

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
  DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:${POSTGRES_PORT}/magic_sale"
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
    python -m venv "$svc_dir/.venv"
    fresh="1"
  fi

  # shellcheck disable=SC1091
  source "$svc_dir/.venv/bin/activate"
  if ! python - <<PY >/dev/null 2>&1
${check_imports}
PY
  then
    need_install="1"
  fi
  deactivate

  if [[ "$fresh" == "1" || "$need_install" == "1" ]]; then
    # shellcheck disable=SC1091
    source "$svc_dir/.venv/bin/activate"
    if [[ "$service" == "prompt-service" ]]; then
      pip install -q -r <(rg -v '^asyncpg==' "$svc_dir/requirements.txt")
      pip install -q 'asyncpg>=0.30,<0.31'
    else
      pip install -q -r "$svc_dir/requirements.txt"
    fi
    deactivate
  fi
}

start_postgres() {
  if pg_isready -h 127.0.0.1 -p "$POSTGRES_PORT" -U postgres -d magic_sale >/dev/null 2>&1; then
    echo "[db] using existing postgres on 127.0.0.1:${POSTGRES_PORT}"
    return
  fi

  if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
    echo "[db] postgres container already running"
  elif docker ps -a --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
    docker start "$POSTGRES_CONTAINER" >/dev/null
  else
    postgres_run_args=(
      -d
      --name "$POSTGRES_CONTAINER"
      -e POSTGRES_USER=postgres
      -e POSTGRES_PASSWORD=postgres
      -e POSTGRES_DB=magic_sale
      -p "${POSTGRES_PORT}:5432"
      -v "${POSTGRES_VOLUME}:/var/lib/postgresql/data"
    )
    if [[ -f "$POSTGRES_INIT_SQL" ]]; then
      postgres_run_args+=(-v "${POSTGRES_INIT_SQL}:/docker-entrypoint-initdb.d/init.sql:ro")
    fi
    docker run "${postgres_run_args[@]}" "$POSTGRES_IMAGE" >/dev/null
  fi

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

ensure_venv "prompt-service"
ensure_venv "models-service"
ensure_venv "order-service"
ensure_venv "mcp-service"
ensure_venv "zalo-service"

resolve_postgres_port
start_postgres

(
  cd "$ROOT_DIR/prompt-service"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  export DATABASE_URL="$DATABASE_URL"
  PYTHONPATH=. alembic upgrade head
  deactivate
)

(
  cd "$ROOT_DIR/order-service"
  source .venv/bin/activate
  export DATABASE_URL="$DATABASE_URL"
  PYTHONPATH=. alembic upgrade head
  deactivate
)

echo "[run] starting prompt + models + order + mcp + zalo polling"
echo "[run] press Ctrl+C to stop all"

trap 'echo; echo "[stop] shutting down..."; kill 0' INT TERM EXIT

(
  cd "$ROOT_DIR/prompt-service"
  source .venv/bin/activate
  export DATABASE_URL="$DATABASE_URL"
  exec python -m uvicorn main:app --host 127.0.0.1 --port 8001
) &

(
  cd "$ROOT_DIR/models-service"
  source .venv/bin/activate
  export MODEL_NAME="$MODEL_NAME"
  export API_KEY="$API_KEY"
  export BASE_URL="$BASE_URL"
  export PROMPT_SERVICE_URL="http://127.0.0.1:8001"
  export MCP_SERVICE_URL="http://127.0.0.1:8004"
  exec python -m uvicorn main:app --host 127.0.0.1 --port 8000
) &

(
  cd "$ROOT_DIR/order-service"
  source .venv/bin/activate
  export DATABASE_URL="$DATABASE_URL"
  exec python -m uvicorn main:app --host 127.0.0.1 --port 8003
) &

(
  cd "$ROOT_DIR/mcp-service"
  source .venv/bin/activate
  export DATABASE_URL="$DATABASE_URL"
  export PROMPT_SERVICE_URL="http://127.0.0.1:8001"
  export ORDER_SERVICE_URL="http://127.0.0.1:8003"
  export MCP_TRANSPORT="http"
  exec python main.py
) &

(
  cd "$ROOT_DIR/zalo-service"
  source .venv/bin/activate
  export ZALO_BOT_TOKEN="$ZALO_BOT_TOKEN"
  export ZALO_BASE_URL="${ZALO_BASE_URL:-https://bot-api.zaloplatforms.com}"
  export MODEL_SERVICE_URL="http://127.0.0.1:8000"
  export WEBHOOK_SECRET_TOKEN="${WEBHOOK_SECRET_TOKEN:-}"
  export LOG_LEVEL="${LOG_LEVEL:-INFO}"
  export TRACE_CHAT_CONTENT="${TRACE_CHAT_CONTENT:-0}"
  exec python main.py --mode polling
) &

wait
