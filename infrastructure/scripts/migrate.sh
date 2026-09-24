#!/bin/bash
# migrate.sh — Run Alembic migrations for all DB-owning services
# Usage: bash scripts/migrate.sh
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infrastructure"

echo "🔄 Running Alembic migrations..."
echo "   Project root: $PROJECT_ROOT"
echo ""

DB_SERVICES=(data-service order-service prompt-service)

for service in "${DB_SERVICES[@]}"; do
    SERVICE_DIR="$PROJECT_ROOT/$service"
    echo "  → Migrating $service..."

    if [ ! -d "$SERVICE_DIR" ]; then
        echo "  ⚠️  Directory $SERVICE_DIR not found, skipping"
        continue
    fi

    if [ ! -f "$SERVICE_DIR/requirements.txt" ]; then
        echo "  ⚠️  No requirements.txt in $service, skipping"
        continue
    fi

    cd "$SERVICE_DIR"

    # Create venv if not present
    if [ ! -d ".venv" ]; then
        echo "     Creating virtual environment..."
        python -m venv .venv
    fi

    # Activate and install deps
    # shellcheck source=/dev/null
    source .venv/bin/activate
    pip install -q -r requirements.txt

    # Run migration
    if [ ! -f "alembic.ini" ]; then
        echo "  ⚠️  No alembic.ini in $service, skipping"
        deactivate
        continue
    fi

    alembic upgrade head
    deactivate

    echo "  ✅ $service migrated"
done

echo ""
echo "✅ All migrations complete"
