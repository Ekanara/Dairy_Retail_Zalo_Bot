#!/bin/bash
# import_data.sh — Import product CSV into data-service via Python script
# Usage: bash scripts/import_data.sh
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CSV_FILE="$PROJECT_ROOT/trash/data/csv/product_infomation.csv"

echo "📦 Importing product data from CSV..."
echo "   CSV path: $CSV_FILE"

if [ ! -f "$CSV_FILE" ]; then
    echo "❌ CSV file not found: $CSV_FILE"
    echo "   Place your product CSV at: trash/data/csv/product_infomation.csv"
    exit 1
fi

DATA_SERVICE_DIR="$PROJECT_ROOT/data-service"

if [ ! -d "$DATA_SERVICE_DIR" ]; then
    echo "❌ data-service directory not found: $DATA_SERVICE_DIR"
    exit 1
fi

cd "$DATA_SERVICE_DIR"

# Activate venv (setup.sh must have run first)
if [ ! -d ".venv" ]; then
    echo "⚠️  No .venv found in data-service. Run 'make setup' first."
    exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate
python -m app.scripts.import_products --csv "$CSV_FILE"
deactivate

echo "✅ Product data imported successfully"
