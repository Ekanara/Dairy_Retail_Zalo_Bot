.PHONY: help setup up down logs health test clean import-products search-products

help:
	@echo "RAG Service - Available commands:"
	@echo ""
	@echo "Setup & Services:"
	@echo "  make setup           - First-time setup (copy .env.example to .env)"
	@echo "  make up              - Start all services"
	@echo "  make down            - Stop all services"
	@echo "  make logs            - Tail logs from all services"
	@echo "  make logs-rag        - Tail logs from RAG service only"
	@echo "  make health          - Check health of all services"
	@echo "  make test            - Run test script"
	@echo "  make clean           - Clean up containers and volumes"
	@echo ""
	@echo "Product Import:"
	@echo "  make import-products - Import products from data-service"
	@echo "  make search-products - Test product search (interactive)"
	@echo "  make delete-products - Delete product collection"
	@echo ""
	@echo "Development:"
	@echo "  make dev-setup       - Create venv and install dependencies"
	@echo "  make dev-run         - Run service locally"

setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ Created .env file from .env.example"; \
		echo "⚠ Please edit .env and add your GEMINI_API_KEY"; \
	else \
		echo ".env already exists"; \
	fi

up:
	docker-compose up -d
	@echo "✓ Services starting..."
	@echo "  RAG API: http://localhost:8006"
	@echo "  Qdrant: http://localhost:6333"
	@echo "  TEI Reranker: http://localhost:8005"
	@echo ""
	@echo "Run 'make health' to check service status"

down:
	docker-compose down

logs:
	docker-compose logs -f

logs-rag:
	docker-compose logs -f rag-service

logs-qdrant:
	docker-compose logs -f qdrant

logs-reranker:
	docker-compose logs -f tei-reranker

health:
	@echo "Checking service health..."
	@echo ""
	@echo "RAG Service:"
	@curl -s http://localhost:8006/api/v1/health | jq . || echo "✗ RAG service not responding"
	@echo ""
	@echo "Qdrant:"
	@curl -s http://localhost:6333/healthz || echo "✗ Qdrant not responding"
	@echo ""
	@echo "TEI Reranker:"
	@curl -s http://localhost:8005/health || echo "✗ TEI reranker not responding"

test:
	@echo "Running test script..."
	@python test_rag.py

clean:
	docker-compose down -v
	@echo "✓ Cleaned up containers and volumes"

# Development commands
dev-setup:
	python -m venv .venv
	.venv/bin/pip install -r requirements.txt
	@echo "✓ Virtual environment created and dependencies installed"
	@echo "  Activate with: source .venv/bin/activate"

dev-run:
	uvicorn main:app --reload --port 8006 --log-level info

dev-test:
	python -m pytest tests/ -v

# Docker commands
build:
	docker-compose build

restart:
	docker-compose restart

ps:
	docker-compose ps

# Product import commands
import-products:
	@echo "Importing products from data-service..."
	@echo "Ensure data-service is running on http://localhost:8002"
	@python scripts/import_products_from_data_service.py \
		--data-service-url http://localhost:8002 \
		--rag-service-url http://localhost:8006 \
		--project-name magic_sale_products \
		--batch-size 10

search-products:
	@echo "Testing product search..."
	@echo "Enter your query (Vietnamese, or leave empty for test suite):"
	@read -r query; \
	if [ -z "$$query" ]; then \
		python scripts/test_product_search.py; \
	else \
		python scripts/test_product_search.py --query "$$query"; \
	fi

delete-products:
	@echo "Deleting product collection..."
	@curl -X DELETE http://localhost:8006/api/v1/collections/magic_sale_products
	@echo ""
	@echo "✓ Collection deleted. Run 'make import-products' to re-import."
