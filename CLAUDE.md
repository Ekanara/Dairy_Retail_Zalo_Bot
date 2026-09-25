# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Magic Sale AI is a Vietnamese e-commerce chatbot platform — a multi-service Python backend that powers an AI sales assistant on Zalo. Users message via Zalo, the AI responds with personalized product recommendations, processes orders, and remembers user preferences. The sales flow follows a SPIN Selling methodology with 5 stages (opening → discovery → support → objection-handling → closing).

## Architecture

Eight FastAPI microservices + PostgreSQL (pgvector) + Redis + Qdrant + TEI reranker:

```
Zalo → zalo-service (8080) → models-service (8000) ──→ prompt-service (8001)
                                    │                ──→ chat-service (8007)
                                    ↓
                              mcp-service (8004) → data-service (8002)
                                                 → order-service (8003)
                                                 → rag-service (8006) → Qdrant + TEI
```

- **models-service** (8000) — AgentScope ReActAgent orchestrator. Fetches personalized prompts, loads chat history, executes MCP tools, injects skill resources per turn. Uses `OpenAIChatModel` + `HttpStatelessClient` for MCP transport.
- **prompt-service** (8001) — Per-user prompt personalization. Stores SOUL/USER/MEMORY markdown in DB, renders via custom Jinja2 loader (`_PerUserLoader`). Templates in `prompt-service/prompt_architechture/`.
- **data-service** (8002) — Product catalog CRUD, CSV import, full-text search.
- **order-service** (8003) — Order lifecycle, stock ledger, ACID inventory transactions via `async with session.begin()`.
- **mcp-service** (8004) — FastMCP tool server. Tools: `search_keyword`, `rag_search`, `rag_hybrid_search`, `create_order`, `view_personal_profile`, `edit_personal_profile`, `list_brands`, `search_by_age`, `search_by_segment`. `HideUserIdMiddleware` strips user_id from tool schemas (injected at runtime by models-service).
- **rag-service** (8006) — Semantic search via Qdrant vector DB + TEI cross-encoder reranker. Health at `/api/v1/health`.
- **chat-service** (8007) — Conversation history. Redis-first read strategy (Redis → PostgreSQL fallback → repopulate Redis). TTL 24h.
- **zalo-service** (8080) — Zalo webhook gateway. Polling mode for local dev (`python main.py --mode polling`).

Each service follows: `app/api/` (routes), `app/services/` (business logic), `app/repositories/` or `app/db/` (data access), `app/core/` (config, logger), `main.py` (entrypoint).

### Inter-service communication

models-service is the hub — on every user message it calls:
- `GET prompt-service/prompts/{user_id}` — fetch rendered system prompt (timeout 10s)
- `GET chat-service/chat/messages?window_id=...&limit=50` — load history (timeout 5s)
- `POST chat-service/chat/messages` — save user/assistant messages
- MCP tools via `streamable-http` transport to mcp-service (which fans out to data/order/rag services)

HTTP clients use `httpx.AsyncClient` singletons with connection pooling (`models-service/app/clients/`).

### Agent orchestration (models-service)

Built with AgentScope's `ReActAgent` + `Toolkit` + `HttpStatelessClient`:
1. Fetch system prompt → inject runtime `user_id` guard (`_inject_runtime_user_id`) to prevent tool-call hallucination
2. Load conversation history into `InMemoryMemory` as `Msg` objects
3. Inject skill instructions from `models-service/skills/sales-conversion/resources/` (01-opening through 05-closing)
4. Run `agent.reply()` (non-streaming) or `agent.reply_stream()` (streaming SSE)

Key files: `models-service/app/services/model_service.py` (orchestration), `models-service/app/clients/model_client.py` (agent setup).

### Prompt architecture (prompt-service)

Modular Jinja2 template system in `prompt-service/prompt_architechture/`:
- `system_prompt.md` — master template, includes others via `{% include "AGENTS.md" %}`
- `IDENTITY.md` — bot persona (nutrition assistant for "Nhà Sữa", an independent retailer; discloses that it is an AI when asked, and never claims to represent a manufacturer)
- `AGENTS.md` — agent behavior rules
- `TOOLS.md` — tool usage instructions
- `SOUL.md`, `USER.md`, `MEMORY.md` — per-user profile templates (stored in DB, rendered per request)

Every turn the agent must call `view_personal_profile(user_id, "SOUL.md"|"USER.md"|"MEMORY.md")` before responding. Skipping this violates the mandatory workflow.

### Skills system (models-service)

Three skill sets in `models-service/skills/`: `sales-conversion` (primary), `pediasure_chatbot`, `ensure_chatbot`.

The main `sales-conversion/SKILL.md` orchestrates phase selection. Resources loaded via `ReadSkillFile(skill_name="sales-conversion", file_path="resources/XX-phase.md")`. Brand-to-segment mapping:
- Ensure/Ensure Gold → adults/elderly/joint health
- Similac → infants 0-12mo
- PediaSure → children 1-10yo poor appetite
- Grow → children 2+ height growth
- Glucerna → diabetics

Critical rule: search tools (search_keyword, rag_search) are gated to phase 03 (support) only, requiring ≥3 data points (who + age + health condition).

### Payment & email flow

**Order creation** (mcp-service `create_order` tool → order-service):
1. ACID inventory check + stock deduction
2. VietQR payment URL generated: `https://img.vietqr.io/image/{BANK_BIN}-{BANK_ACCOUNT_NO}-{VIETQR_TEMPLATE}.png?amount=...&addInfo=DH{order_code}`
3. HTML confirmation email sent via aiosmtplib (Gmail SMTP, requires App Password)
4. Email includes product details, total, QR payment image

**SePay webhook** (order-service `POST /webhook/sepay`):
1. Verify API key from `Authorization: Apikey {SEPAY_API_KEY}` header
2. Extract order code `DH{8 hex}` from transfer content via regex
3. Match to pending order, verify amount ≥ total
4. Auto-confirm order status → `confirmed`
5. Send thank-you Zalo message via `POST zalo-service/internal/send-message`

### Zalo internal API

zalo-service exposes internal endpoints for other services (not webhook-facing):
- `POST /internal/send-message` — send text message to Zalo user
- `POST /internal/send-photo` — send image to Zalo user

### Vietnamese-specific search logic (mcp-service)

`mcp-service/app/tools/search_tool.py` maps Vietnamese terms to enums:
- Segments: trẻ em→children, người già→elderly, phụ nữ→women, tiểu đường→diabetic, mang thai→pregnant_mothers, cho con bú→breastfeeding_mothers
- Ages: tháng tuổi→months, tuổi→years, mapped to ranges (age_0m_6m, age_6m_36m, age_4y_12y, etc.)
- Stopword filtering for Vietnamese common words

## Development Commands

### Docker (full stack)
```bash
cd infrastructure
make setup          # First-time: .env copy, pip install, migrate, import
make up             # Start all services
make down           # Stop all
make health         # Health check all 8 services + Qdrant + TEI
make logs           # Tail all logs
make logs-<service> # Tail specific (e.g. make logs-models-service)
make migrate        # Run Alembic migrations for all DB services
make import         # Import product CSV
make dev-infra      # Start only PostgreSQL + Redis + Qdrant + TEI
make dev-start      # Start all 8 services locally (no Docker, requires venvs)
make psql           # Connect to PostgreSQL
make redis-cli      # Connect to Redis
make import-products # Import products into RAG
make restart-<svc>  # Restart specific service
make shell-<svc>    # Shell into container
```

Note: Docker exposes PostgreSQL on host port **5434** (not 5432). PostgreSQL init script (`infrastructure/postgres/init.sql`) creates extensions: `uuid-ossp`, `pgcrypto`, `vector` (pgvector).

### Local development (per-service)
```bash
cd <service-name>
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port <port>
```

Service ports: models=8000, prompt=8001, data=8002, order=8003, mcp=8004, rag=8006, chat=8007, zalo=8080.

### Local dev scripts
```bash
./scripts/chat-up.sh     # Start all services locally (handles venv/pip/migrations)
./scripts/chat-down.sh   # Graceful shutdown
./scripts/chat-status.sh # Process status check
./scripts/chat-logs.sh   # Log tailing
```

### Database migrations (per-service with Alembic)
```bash
cd <service-name>
alembic upgrade head
```
Services with DB migrations: chat-service, data-service, order-service, prompt-service, mcp-service.

### Tests
```bash
python -m unittest discover -s trash/tests -p 'test_*.py'
cd models-service && python -m pytest tests/
cd rag-service && python scripts/test_product_search.py
```

## Coding Conventions

- **Async everywhere** — all I/O uses async (FastAPI, SQLAlchemy asyncio, asyncpg, httpx.AsyncClient).
- **Structured JSON logging** via `app/core/logger.py` — `logger.info("event.name", key=value)`. No `print()`.
- **pydantic-settings** for config — every service has `app/core/config.py` with `BaseSettings` + `@lru_cache`.
- **Type hints** on all functions. Pydantic models for request/response schemas.
- **snake_case** for modules, functions, variables.
- **Conventional Commits** — `feat:`, `fix:`, `chore:` prefixes. Keep commits focused by service.
- **Virtualenv per service** — each service has its own `requirements.txt` and `.venv/`.

## Key Environment Variables

Required for models-service: `MODEL_NAME`, `API_KEY`, `BASE_URL` (OpenAI-compatible endpoint), `LLM_TIMEOUT=60`.
Zalo: `ZALO_BOT_TOKEN`, `WEBHOOK_SECRET_TOKEN`.
Database: `DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/magic_sale` (single shared DB for all services).
Embedding/RAG: `EMBEDDING_MODEL_NAME`, `EMBEDDING_BASE_URL`, Qdrant at port 6333, TEI reranker at port 8005.
Inter-service timeouts: `PROMPT_SERVICE_TIMEOUT=10`, `CHAT_SERVICE_TIMEOUT=5`.
Email (mcp-service): `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER`, `SMTP_PASSWORD` (Gmail App Password), `EMAIL_FROM`, `EMAIL_ENABLED=true/false`.
Payment (mcp-service): `BANK_BIN=970407` (Techcombank), `BANK_ACCOUNT_NO`, `BANK_ACCOUNT_NAME`, `VIETQR_TEMPLATE=compact2`.
SePay (order-service): `SEPAY_API_KEY`.
RAG tuning (rag-service): `DEFAULT_TOP_K=20`, `DEFAULT_TOP_N=5`, `RRF_K=60`, `MMR_LAMBDA=0.7`.
See `infrastructure/.env.example` and per-service `.env.example` files.
