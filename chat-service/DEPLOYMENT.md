# chat-service — Deployment Guide

## Quick Start

### 1. **Using Docker Compose (Recommended)**

```bash
cd infrastructure

# Start all services including chat-service
make up

# Check health
make health

# View logs
make logs-chat-service

# Run migrations
make migrate
```

The service will be available at: **http://localhost:8007**

---

### 2. **Local Development (Without Docker)**

#### Prerequisites
- Python 3.11+
- PostgreSQL 16 (with pgvector)
- Redis 7

#### Step-by-step

```bash
# 1. Start infrastructure
cd infrastructure
make dev-infra  # Starts PostgreSQL + Redis + Qdrant + TEI

# 2. Setup chat-service
cd ../chat-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your settings

# 4. Run migrations
alembic upgrade head

# 5. Start service
uvicorn main:app --host 0.0.0.0 --port 8007 --reload
```

---

## Environment Configuration

### Minimal `.env` for local dev:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5434/magic_sale
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=INFO
SERVICE_PORT=8007
CACHE_TTL=86400
DEFAULT_TOP_K=100
```

### Docker Compose (auto-configured):

```yaml
environment:
  DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/magic_sale
  REDIS_URL: redis://redis:6379/0
  SERVICE_PORT: 8007
```

---

## Database Migration

### Create new migration

```bash
cd chat-service
alembic revision --autogenerate -m "description"
```

### Apply migrations

```bash
alembic upgrade head
```

### Rollback migration

```bash
alembic downgrade -1
```

---

## Testing

### 1. **Health check**

```bash
curl http://localhost:8007/health
```

Expected:
```json
{"status": "ok", "service": "chat-service"}
```

### 2. **Save a message**

```bash
curl -X POST http://localhost:8007/chat/messages \
  -H "Content-Type: application/json" \
  -d '{
    "window_id": "test_user_123",
    "role": "user",
    "content": "Xin chào!",
    "metadata": {}
  }'
```

### 3. **Fetch messages**

```bash
curl "http://localhost:8007/chat/messages?window_id=test_user_123&limit=10"
```

### 4. **Run test suite**

```bash
cd chat-service
python scripts/test_api.py
```

---

## Production Checklist

### Before deployment:

- [ ] Set `LOG_LEVEL=WARNING` in production
- [ ] Configure proper `CACHE_TTL` (default 24h)
- [ ] Set up database backups
- [ ] Configure connection pool sizes (see `app/db/database.py`)
- [ ] Enable Redis persistence (see `docker-compose.yml`)
- [ ] Set up monitoring/alerting (health endpoint: `/health`)
- [ ] Review and tune `DEFAULT_TOP_K` based on usage

### Security:

- [ ] Use strong PostgreSQL password
- [ ] Enable Redis AUTH if exposed
- [ ] Set up firewall rules
- [ ] Use HTTPS reverse proxy (nginx)
- [ ] Rotate credentials regularly

### Performance tuning:

```python
# app/db/database.py
pool_size=10,        # Increase for high concurrency
max_overflow=20,

# app/services/redis_service.py
max_connections=20,  # Redis pool size
```

---

## Monitoring

### Key metrics to track:

1. **Latency**
   - Cache hit: <5ms
   - Cache miss: ~20-50ms
   - Write: ~20-30ms

2. **Cache hit rate**
   - Target: >80% cache hits
   - Monitor via logs: `redis.cache_hit` vs `redis.cache_miss`

3. **Error rate**
   - Monitor logs for `ERROR` level entries
   - Watch for `redis.unavailable` or `db.unavailable`

### Health check endpoint

```bash
GET /health
```

Returns `200 OK` if service is running (does not check DB/Redis connectivity).

---

## Troubleshooting

### Service won't start

1. Check PostgreSQL connectivity:
   ```bash
   psql -h localhost -p 5434 -U postgres -d magic_sale
   ```

2. Check Redis connectivity:
   ```bash
   redis-cli -h localhost -p 6379 ping
   ```

3. Check logs:
   ```bash
   docker compose logs chat-service
   ```

### Slow queries

1. Verify indexes exist:
   ```sql
   \d+ chat_messages
   ```

2. Check query plans:
   ```sql
   EXPLAIN ANALYZE
   SELECT * FROM chat_messages
   WHERE window_id = 'test'
   ORDER BY created_at DESC
   LIMIT 100;
   ```

### Redis cache not working

1. Check Redis connection:
   ```bash
   docker compose exec redis redis-cli
   > PING
   PONG
   ```

2. Verify cache keys:
   ```bash
   > KEYS chat:*
   > ZREVRANGE chat:window:test_user_123 0 9
   ```

3. Clear cache if needed:
   ```bash
   > DEL chat:window:test_user_123
   ```

---

## Scaling

### Horizontal scaling

- chat-service is **stateless** (Redis/PostgreSQL hold state)
- Safe to run multiple instances behind a load balancer
- No inter-service communication needed

### Vertical scaling

- Increase PostgreSQL connection pool size
- Increase Redis max_connections
- Add more memory for Redis cache

### Database optimization

- Partition `chat_messages` by `created_at` (monthly/quarterly)
- Archive old messages to cold storage
- Implement TTL-based cleanup job

---

## Integration Example

### From models-service:

```python
import httpx

async def get_conversation_history(window_id: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "http://chat-service:8007/chat/messages",
            params={"window_id": window_id, "limit": 50},
            timeout=5.0
        )
        resp.raise_for_status()
        return resp.json()["messages"]

async def save_conversation_turn(window_id: str, user_msg: str, ai_msg: str):
    async with httpx.AsyncClient() as client:
        # Save user message
        await client.post(
            "http://chat-service:8007/chat/messages",
            json={
                "window_id": window_id,
                "role": "user",
                "content": user_msg
            }
        )
        # Save assistant response
        await client.post(
            "http://chat-service:8007/chat/messages",
            json={
                "window_id": window_id,
                "role": "assistant",
                "content": ai_msg
            }
        )
```

---

## Support

For issues or questions:
- Check logs: `make logs-chat-service`
- Review [README.md](README.md)
- Check infrastructure docs: `../infrastructure/README.md`
