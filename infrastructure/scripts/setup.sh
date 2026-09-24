#!/bin/bash
# setup.sh — First-time full environment setup for Magic Sale AI
# Usage: bash scripts/setup.sh
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infrastructure"

echo "🚀 Magic Sale AI — Full Setup"
echo "================================"
echo "   Project root: $PROJECT_ROOT"
echo ""

ALL_SERVICES=(data-service order-service prompt-service models-service mcp-service zalo-service)

# ── Step 1: Copy .env files if missing ────────────────────────────────────────
echo "📋 Setting up .env files..."
for service in "${ALL_SERVICES[@]}"; do
    ENV_FILE="$PROJECT_ROOT/$service/.env"
    EXAMPLE_FILE="$PROJECT_ROOT/$service/.env.example"

    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$EXAMPLE_FILE" ]; then
            cp "$EXAMPLE_FILE" "$ENV_FILE"
            echo "  ✅ Created $service/.env from .env.example"
        else
            echo "  ⚠️  No .env.example found for $service — skipping"
        fi
    else
        echo "  ⏭️  $service/.env already exists, skipping"
    fi
done

# ── Step 2: Install Python deps per service ───────────────────────────────────
echo ""
echo "📦 Installing Python dependencies..."
for service in "${ALL_SERVICES[@]}"; do
    SERVICE_DIR="$PROJECT_ROOT/$service"

    if [ ! -d "$SERVICE_DIR" ]; then
        echo "  ⚠️  $service directory not found, skipping"
        continue
    fi

    echo "  → Installing $service..."
    cd "$SERVICE_DIR"

    python -m venv .venv
    # shellcheck source=/dev/null
    source .venv/bin/activate
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    deactivate

    echo "  ✅ $service ready"
done

# ── Step 3: Start infrastructure (Postgres + Redis) ───────────────────────────
echo ""
echo "🐳 Starting PostgreSQL + Redis..."
cd "$INFRA_DIR"
docker compose up -d postgres redis

echo "  ⏳ Waiting for PostgreSQL to be ready..."
# Poll until pg_isready succeeds (max 30s)
RETRIES=30
until docker compose exec -T postgres pg_isready -U postgres -d magic_sale > /dev/null 2>&1; do
    RETRIES=$((RETRIES - 1))
    if [ "$RETRIES" -le 0 ]; then
        echo "  ❌ PostgreSQL did not become ready in time"
        exit 1
    fi
    sleep 1
done
echo "  ✅ PostgreSQL is ready"

# ── Step 4: Run Alembic migrations ────────────────────────────────────────────
echo ""
bash "$INFRA_DIR/scripts/migrate.sh"

# ── Step 5: Import CSV product data ───────────────────────────────────────────
echo ""
bash "$INFRA_DIR/scripts/import_data.sh"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "================================"
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Fill in API keys in each service's .env:"
echo "     - models-service/.env  → API_KEY, BASE_URL"
echo "     - zalo-service/.env    → ZALO_BOT_TOKEN"
echo "     - mcp-service/.env     → SMTP_USER, SMTP_PASSWORD"
echo ""
echo "  2. Start all services (Docker):"
echo "     cd infrastructure && docker compose up -d"
echo ""
echo "  3. Or start services locally (non-Docker):"
echo "     cd infrastructure && make dev-start"
echo ""
echo "  4. Check health:"
echo "     cd infrastructure && make health"
echo ""
