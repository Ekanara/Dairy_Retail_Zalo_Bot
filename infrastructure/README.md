# Infrastructure — Magic Sale AI

Quản lý toàn bộ infrastructure cho hệ thống Magic Sale AI: 6 Python microservices + PostgreSQL (pgvector) + Redis.

## Cấu trúc thư mục

```
infrastructure/
├── docker-compose.yml          # Orchestrate tất cả 8 services
├── Makefile                    # CLI shortcuts cho mọi tác vụ thường gặp
├── .env.example                # Shared infrastructure env vars mẫu
├── dockerfiles/
│   └── Dockerfile.python       # Reusable Python 3.11-slim image (dùng cho tất cả services)
├── nginx/
│   └── nginx.conf              # Reverse proxy — production (optional)
├── postgres/
│   └── init.sql                # Khởi tạo extensions: uuid-ossp, pgcrypto, vector
└── scripts/
    ├── setup.sh                # First-time full setup (chạy 1 lần)
    ├── migrate.sh              # Chạy Alembic migrations cho tất cả DB services
    └── import_data.sh          # Import CSV product data vào data-service
```

---

## Quick Start (Docker — khuyến nghị)

```bash
cd infrastructure

# 1. Full setup lần đầu (copy .env, pip install, migrate, import CSV)
make setup

# 2. Điền API keys bắt buộc
vim ../models-service/.env   # API_KEY, BASE_URL (LLM endpoint)
vim ../zalo-service/.env     # ZALO_BOT_TOKEN
vim ../mcp-service/.env      # SMTP_USER, SMTP_PASSWORD

# 3. Start tất cả services
make up

# 4. Kiểm tra health
make health
```

---

## Local Dev (không Docker)

```bash
cd infrastructure

# Start chỉ PostgreSQL + Redis
make dev-infra

# Chạy migration và import dữ liệu
make migrate
make import

# Start tất cả 6 services locally (một terminal, Ctrl+C để dừng)
make dev-start
```

---

## Bảng tham chiếu Commands

| Command | Mô tả |
|---------|-------|
| `make up` | Start tất cả containers |
| `make down` | Stop tất cả containers |
| `make build` | Rebuild Docker images (no-cache) |
| `make logs` | Tail logs tất cả services |
| `make logs-zalo-service` | Tail logs của zalo-service |
| `make restart-zalo-service` | Restart zalo-service container |
| `make shell-postgres` | Mở bash trong postgres container |
| `make ps` | Xem trạng thái containers |
| `make health` | Kiểm tra `/health` tất cả services |
| `make psql` | Kết nối PostgreSQL CLI |
| `make redis-cli` | Kết nối Redis CLI |
| `make migrate` | Chạy Alembic migrations |
| `make import` | Import product CSV |
| `make setup` | Full first-time setup |
| `make dev-infra` | Start chỉ DB + Redis |
| `make dev-start` | Start 6 services locally |

---

## Service Dependency Graph

```
postgres (5433)
    ├── data-service    :8002   (product catalog CRUD)
    ├── order-service   :8003   (order + stock management)
    ├── prompt-service  :8001   (per-user system prompt)
    └── mcp-service     :8004   (MCP tools: search, RAG, order, profile)
            │
redis (6379)
    └── (short-term chat history — top 5 msgs/user)

models-service   :8000   ← prompt-service :8001
                         ← mcp-service    :8004

zalo-service     :8080   ← models-service :8000
```

---

## Notes Quan Trọng

### PostgreSQL
- Image `pgvector/pgvector:pg16` đã bao gồm sẵn extension `pgvector` — **không cần** cài thêm.
- `init.sql` chỉ chạy **một lần** khi volume `postgres_data` chưa tồn tại.
- Để reset DB: `docker compose down -v` (xóa volumes) rồi `make up`.

### Redis
- Config: `maxmemory 256mb`, eviction policy `allkeys-lru` (tự xóa key cũ nhất khi đầy).
- Dữ liệu được persist với `appendonly yes`.

### Dockerfile.python
- Một Dockerfile duy nhất dùng cho tất cả 6 Python services.
- Build context là **thư mục của từng service** (`../data-service`, v.v.) nên `requirements.txt` của mỗi service được copy đúng.
- Chạy với user `appuser` (uid 1000) — không phải root.

### Nginx (Production)
- Mặc định **disabled** trong docker-compose.yml (commented out).
- Uncomment section `nginx:` trong docker-compose để bật.
- `nginx.conf` chặn `/api/chat` chỉ cho phép Docker network và localhost — AI endpoint không lộ ra internet.

### DATABASE_URL Override
- Mỗi service có `.env` riêng với `DATABASE_URL` trỏ về `localhost`.
- docker-compose **override** `DATABASE_URL` để trỏ về hostname `postgres` (container name) — đảm bảo kết nối đúng trong Docker network.

### Zalo Token
- `ZALO_BOT_TOKEN` **không được log** — đã xử lý trong zalo-service theo rule #7 của CLAUDE.md.

---

## Troubleshooting

**PostgreSQL không khởi động được:**
```bash
make logs-postgres
# Thường do port 5433 đã bị chiếm
sudo lsof -i :5433
```

**Service không kết nối được DB:**
```bash
# Kiểm tra network
docker compose exec data-service ping postgres
# Kiểm tra DATABASE_URL override
docker compose exec data-service env | grep DATABASE_URL
```

**Migration lỗi:**
```bash
# Kiểm tra alembic.ini tồn tại trong service
ls ../data-service/alembic.ini
# Chạy thủ công
cd ../data-service && source .venv/bin/activate && alembic upgrade head
```
