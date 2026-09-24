.PHONY: help up down build logs migrate import setup dev-infra dev-start ps health psql redis-cli

PROJECT_ROOT := $(shell cd .. && pwd)

help: ## Show this help message
	@grep -E '^[a-zA-Z_%-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ── Docker Compose ──────────────────────────────────────────────────────────

up: ## Start all services (Docker Compose)
	docker compose up -d

down: ## Stop all services
	docker compose down

build: ## Rebuild all Docker images (no cache)
	docker compose build --no-cache

logs: ## Tail logs from all services
	docker compose logs -f

logs-%: ## Tail logs from specific service (e.g. make logs-zalo-service)
	docker compose logs -f $*

ps: ## Show running containers and their status
	docker compose ps

restart-%: ## Restart a specific service (e.g. make restart-zalo-service)
	docker compose restart $*

shell-%: ## Open bash shell inside a container (e.g. make shell-postgres)
	docker compose exec $* bash

# ── Database ─────────────────────────────────────────────────────────────────

psql: ## Connect to PostgreSQL (magic_sale database)
	docker compose exec postgres psql -U postgres -d magic_sale

redis-cli: ## Connect to Redis CLI
	docker compose exec redis redis-cli

migrate: ## Run Alembic migrations for all DB services
	bash scripts/migrate.sh

import: ## Import product CSV data into data-service
	bash scripts/import_data.sh

# ── Setup & Dev ──────────────────────────────────────────────────────────────

setup: ## Full first-time setup: .env copy, pip install, migrate, import
	bash scripts/setup.sh

dev-infra: ## Start only PostgreSQL + Redis + Qdrant + TEI for local development
	docker compose up -d postgres redis qdrant tei-reranker

dev-start: ## Start all 8 services locally without Docker (requires venvs set up)
	@echo "Starting all services locally (Ctrl+C to stop all)..."
	@trap 'kill 0' INT; \
	(cd $(PROJECT_ROOT)/prompt-service  && source .venv/bin/activate && uvicorn main:app --port 8001 --reload) & \
	(cd $(PROJECT_ROOT)/data-service    && source .venv/bin/activate && uvicorn main:app --port 8002 --reload) & \
	(cd $(PROJECT_ROOT)/order-service   && source .venv/bin/activate && uvicorn main:app --port 8003 --reload) & \
	(cd $(PROJECT_ROOT)/mcp-service     && source .venv/bin/activate && python main.py) & \
	(cd $(PROJECT_ROOT)/models-service  && source .venv/bin/activate && uvicorn main:app --port 8000 --reload) & \
	(cd $(PROJECT_ROOT)/zalo-service    && source .venv/bin/activate && uvicorn main:app --port 8080 --reload) & \
	(cd $(PROJECT_ROOT)/rag-service     && source .venv/bin/activate && uvicorn main:app --port 8006 --reload) & \
	(cd $(PROJECT_ROOT)/chat-service    && source .venv/bin/activate && uvicorn main:app --port 8007 --reload) & \
	wait

# ── Health Checks ─────────────────────────────────────────────────────────────

health: ## Check /health endpoint of all HTTP services
	@echo "Checking service health..."
	@curl -sf http://localhost:8001/health > /dev/null && echo "  ✅ prompt-service  :8001" || echo "  ❌ prompt-service  :8001"
	@curl -sf http://localhost:8002/health > /dev/null && echo "  ✅ data-service    :8002" || echo "  ❌ data-service    :8002"
	@curl -sf http://localhost:8003/health > /dev/null && echo "  ✅ order-service   :8003" || echo "  ❌ order-service   :8003"
	@curl -sf http://localhost:8004/health > /dev/null && echo "  ✅ mcp-service     :8004" || echo "  ❌ mcp-service     :8004"
	@curl -sf http://localhost:8000/health > /dev/null && echo "  ✅ models-service  :8000" || echo "  ❌ models-service  :8000"
	@curl -sf http://localhost:8080/health > /dev/null && echo "  ✅ zalo-service    :8080" || echo "  ❌ zalo-service    :8080"
	@curl -sf http://localhost:8006/api/v1/health > /dev/null && echo "  ✅ rag-service     :8006" || echo "  ❌ rag-service     :8006"
	@curl -sf http://localhost:8007/health > /dev/null && echo "  ✅ chat-service    :8007" || echo "  ❌ chat-service    :8007"
	@curl -sf http://localhost:6333/healthz > /dev/null && echo "  ✅ qdrant          :6333" || echo "  ❌ qdrant          :6333"
	@curl -sf http://localhost:8005/health > /dev/null && echo "  ✅ tei-reranker    :8005" || echo "  ❌ tei-reranker    :8005"

import-products: ## Import products from data-service into RAG
	@echo "Importing products into RAG service..."
	@cd $(PROJECT_ROOT)/rag-service && python scripts/import_products_from_data_service.py

search-products: ## Test product search in RAG service
	@echo "Testing product search..."
	@cd $(PROJECT_ROOT)/rag-service && python scripts/test_product_search.py
