#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/scripts/logs"

mkdir -p "$LOG_DIR"

echo "Tailing logs (Ctrl+C to exit):"
tail -n 80 -f \
  "$LOG_DIR/prompt-service.log" \
  "$LOG_DIR/chat-service.log" \
  "$LOG_DIR/models-service.log" \
  "$LOG_DIR/order-service.log" \
  "$LOG_DIR/mcp-service.log" \
  "$LOG_DIR/rag-service.log" \
  "$LOG_DIR/zalo-service.log" 2>/dev/null
