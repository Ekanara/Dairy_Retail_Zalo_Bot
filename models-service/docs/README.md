# models-service — AI Model Gateway

## Tổng Quan

`models-service` là cổng kết nối trung tâm tới bất kỳ AI model nào tương thích OpenAI API. Dịch vụ này dùng **Pydantic AI** để quản lý agent lifecycle, hỗ trợ streaming/non-streaming và tích hợp với `prompt-service` để lấy system prompt cá nhân hoá theo từng UserID.

---

## Kiến Trúc

```
models-service/
├── app/
│   ├── core/
│   │   ├── config.py          # Env: MODEL_NAME, API_KEY, BASE_URL
│   │   └── logger.py          # Structured logger (JSON) — NO print()
│   ├── clients/
│   │   └── model_client.py    # Pydantic AI OpenAI-compatible client
│   ├── services/
│   │   ├── model_service.py   # Business logic: stream + non-stream
│   │   └── prompt_fetcher.py  # Gọi prompt-service lấy system prompt theo UserID
│   ├── schemas/
│   │   ├── request.py         # ChatRequest (user_id, messages, stream)
│   │   └── response.py        # ChatResponse / StreamChunk
│   └── api/
│       └── routes.py          # FastAPI router: POST /chat, POST /chat/stream
├── docs/
│   └── README.md              # (file này)
├── .env
└── main.py
```

---

## Techstack

| Thư viện | Mục đích |
|---|---|
| `pydantic-ai` | Agent lifecycle, type-safe prompting |
| `openai` (python) | OpenAI-compatible HTTP client |
| `fastapi` | REST API |
| `asyncio` | Async I/O toàn hệ thống |
| `httpx` | Async HTTP client gọi prompt-service |

---

## Cấu Hình `.env`

```env
# BẮT BUỘC — thiếu 1 trong 3 sẽ dừng service ngay khi start
MODEL_NAME=gpt-4.1-mini
API_KEY=your_api_key_here
BASE_URL=https://api.openai.com/v1

# Địa chỉ của prompt-service để lấy system prompt
PROMPT_SERVICE_URL=http://localhost:8001

# Logging
LOG_LEVEL=INFO
```

> ⚠️ `BASE_URL` phải trỏ đến API endpoint (có `/v1`), không phải trang web.

---

## API Endpoints

### `POST /chat` — Non-streaming

**Request:**
```json
{
  "user_id": "zalo_user_abc123",
  "messages": [
    { "role": "user", "content": "Tư vấn sữa cho bé 6 tháng tuổi" }
  ],
  "stream": false
}
```

**Response:**
```json
{
  "message": { "role": "assistant", "content": "..." },
  "usage": { "prompt_tokens": 45, "completion_tokens": 120 }
}
```

---

### `POST /chat/stream` — SSE Streaming

**Response:** `text/event-stream`
```
data: {"delta": "Chào bạn"}
data: {"delta": ", bé 6 tháng..."}
data: [DONE]
```

---

## Flow Xử Lý

```
[Request user_id + messages]
        ↓
[prompt_fetcher → prompt-service GET /prompts/{user_id}]
        ↓
[Build PydanticAI Agent với system prompt cá nhân hoá]
        ↓
[model_client gọi OpenAI-compatible API]
        ↓
[Stream hoặc non-stream response]
```

---

## Nguyên Tắc Code

- ❌ KHÔNG dùng `print()` — dùng `logger.info()` / `logger.error()` với JSON structured
- ❌ KHÔNG dùng `try/except` chung chung — bắt lỗi cụ thể và log đầy đủ context
- ✅ Log mọi request: `user_id`, `model`, `latency_ms`, `token_count`
- ✅ Async toàn bộ: dùng `async def` + `await` cho tất cả I/O

---

## Chạy Local

```bash
cd models-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

---

## Logging Format Chuẩn

```json
{
  "timestamp": "2026-03-13T22:35:00+07:00",
  "level": "INFO",
  "service": "models-service",
  "event": "chat_request",
  "user_id": "zalo_user_abc123",
  "model": "gpt-4.1-mini",
  "stream": false,
  "latency_ms": 1204
}
```
