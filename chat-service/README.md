# chat-service

**Conversation history storage and caching service for Dairy AI.**

Fast top-K message retrieval using Redis (ZSET) + PostgreSQL persistence.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│          chat-service (port 8007)               │
├─────────────────────────────────────────────────┤
│  FastAPI + Redis (cache) + PostgreSQL (store)  │
│                                                 │
│  Redis: Top-K cache (ZSET) - sub-second reads  │
│  PostgreSQL: Long-term storage + full history  │
└─────────────────────────────────────────────────┘
```

### Key Features

- **Dual-key lookup**: Query by `user_id` (UUID) or `window_id` (Zalo user ID)
- **Redis-first caching**: <5ms read latency for cached data
- **Automatic cache population**: Cache miss → fetch from DB → populate cache
- **Top-K queries**: Default 100 messages, configurable up to 1000
- **ACID guarantees**: PostgreSQL as source of truth

### Cache Strategy

1. **Read**: Redis → fallback PostgreSQL → populate Redis
2. **Write**: PostgreSQL first → async update Redis
3. **TTL**: 24 hours (configurable via `CACHE_TTL`)

---

## API Endpoints

### `POST /chat/messages`
Save a new chat message.

**Request body:**
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",  // optional
  "window_id": "zalo_user_123",                       // required
  "role": "user",                                     // user|assistant|system
  "content": "Xin chào!",
  "metadata": {}                                      // optional
}
```

**Response:** `201 Created`
```json
{
  "id": "...",
  "user_id": "...",
  "window_id": "zalo_user_123",
  "role": "user",
  "content": "Xin chào!",
  "metadata": {},
  "created_at": "2025-03-24T12:00:00Z"
}
```

---

### `GET /chat/messages`
Fetch top-K messages (newest first).

**Query parameters:**
- `user_id` (optional): Filter by internal user UUID
- `window_id` (optional): Filter by Zalo user ID
- `limit` (optional): Max messages (default 100, max 1000)

**At least one of `user_id` or `window_id` must be provided.**

**Response:** `200 OK`
```json
{
  "messages": [...],
  "total": 42,
  "from_cache": true
}
```

---

### `GET /chat/user-id`
Look up internal `user_id` from `window_id`.

**Query parameters:**
- `window_id` (required): Zalo user ID

**Response:** `200 OK`
```json
{
  "window_id": "zalo_user_123",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "message_count": 42
}
```

---

### `DELETE /chat/messages/{message_id}`
Delete a chat message by ID.

**Response:** `204 No Content`

---

### `GET /health`
Liveness probe.

**Response:** `200 OK`
```json
{
  "status": "ok",
  "service": "chat-service"
}
```

---

## Database Schema

### `chat_messages` table

| Column      | Type               | Description                                |
|-------------|--------------------|--------------------------------------------|
| id          | UUID               | Primary key                                |
| user_id     | UUID (nullable)    | Internal user UUID                         |
| window_id   | VARCHAR(255)       | Zalo user ID (always present)              |
| role        | VARCHAR(50)        | 'user' \| 'assistant' \| 'system'          |
| content     | TEXT               | Message text                               |
| metadata    | JSONB              | Extensible metadata (tool_calls, etc.)     |
| created_at  | TIMESTAMPTZ        | Message timestamp                          |

**Indexes:**
- `(user_id, created_at DESC)` — fast top-K by user_id
- `(window_id, created_at DESC)` — fast top-K by window_id
- `(window_id)` — fast user_id lookup

---

## Local Development

### 1. Install dependencies

```bash
cd chat-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your database credentials
```

### 3. Run migrations

```bash
alembic upgrade head
```

### 4. Start the service

```bash
uvicorn main:app --host 0.0.0.0 --port 8007 --reload
```

Service will be available at: http://localhost:8007

Interactive docs: http://localhost:8007/docs

---

## Docker Deployment

### Start all services (including chat-service)

```bash
cd infrastructure
make up
```

### Check health

```bash
make health
```

### View logs

```bash
make logs-chat-service
```

---

## Configuration

Environment variables (see [.env.example](.env.example)):

| Variable        | Default                                      | Description                       |
|-----------------|----------------------------------------------|-----------------------------------|
| DATABASE_URL    | postgresql+asyncpg://...                     | PostgreSQL connection string      |
| REDIS_URL       | redis://localhost:6379/0                     | Redis connection string           |
| LOG_LEVEL       | INFO                                         | Logging level                     |
| SERVICE_PORT    | 8007                                         | Service port                      |
| CACHE_TTL       | 86400                                        | Redis cache TTL (seconds)         |
| DEFAULT_TOP_K   | 100                                          | Default message limit             |

---

## Redis Data Structure

### Key pattern
```
chat:user:{user_id}      # Messages for a user_id
chat:window:{window_id}  # Messages for a window_id
```

### ZSET structure
```
Score: Unix timestamp (created_at)
Value: JSON-serialized message dict
```

### Example Redis commands

```bash
# View top 10 messages for a user
ZREVRANGE chat:window:zalo_user_123 0 9

# Count total messages
ZCARD chat:window:zalo_user_123

# Flush cache for a window
DEL chat:window:zalo_user_123
```

---

## Integration with Other Services

### models-service → chat-service
Before calling the AI model, fetch conversation history:

```python
import httpx

async def get_chat_history(window_id: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://chat-service:8007/chat/messages",
            params={"window_id": window_id, "limit": 50}
        )
        data = response.json()
        return data["messages"]
```

### After AI response, save to history:

```python
async def save_message(window_id: str, role: str, content: str):
    async with httpx.AsyncClient() as client:
        await client.post(
            "http://chat-service:8007/chat/messages",
            json={
                "window_id": window_id,
                "role": role,
                "content": content,
                "metadata": {}
            }
        )
```

---

## Performance

- **Cache hit read latency**: <5ms
- **Cache miss (DB fetch)**: ~20-50ms
- **Write latency**: ~20-30ms (PostgreSQL + Redis update)

### Recommended limits
- Keep `limit` ≤ 200 for optimal performance
- For longer history, implement pagination/cursor

---

## License

Part of Dairy AI — see [LICENSE](../LICENSE)
