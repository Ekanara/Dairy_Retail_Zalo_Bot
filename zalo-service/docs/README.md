# zalo-service — Zalo Webhook Gateway

## Tổng Quan

`zalo-service` là cổng vào/ra của hệ thống với nền tảng Zalo OA (Official Account). Nhận tin nhắn từ user qua webhook Zalo, route tới `models-service` để xử lý AI, rồi push câu trả lời ngược lại Zalo API.

---

## Kiến Trúc

```
zalo-service/
├── app/
│   ├── core/
│   │   ├── config.py          # ZALO_BOT_TOKEN, ZALO_BASE_URL, env vars
│   │   └── logger.py          # Structured logger
│   ├── clients/
│   │   ├── zalo_client.py     # Gọi Zalo API để gửi tin nhắn
│   │   └── model_client.py    # Gọi models-service (HTTP)
│   ├── schemas/
│   │   ├── zalo_event.py      # Parse event Zalo inbound
│   │   └── zalo_message.py    # Payload gửi ra Zalo
│   ├── services/
│   │   └── chat_service.py    # Orchestrator: nhận → xử lý → gửi
│   └── api/
│       ├── webhook.py         # POST /webhook — nhận event từ Zalo
│       └── health.py          # GET /health — health check
├── docs/
│   └── README.md              # (file này)
├── .env
└── main.py
```

---

## Flow Chính

```
[Zalo Platform]
      │ POST /webhook (event: message_from_user)
      ↓
[zalo-service / webhook.py]
      │ Parse ZaloEvent (user_id, message_text)
      ↓
[chat_service.py]
      │ POST models-service /chat (user_id, messages)
      ↓
[models-service] → Pydantic AI → LLM
      │ Return AI response
      ↓
[zalo_client.py]
      │ POST Zalo API /message (send reply to user_id)
      ↓
[Zalo Platform → User phone]
```

---

## Modes Hoạt Động

### Webhook (Production)

```bash
python main.py --mode webhook --host 0.0.0.0 --port 8080
```

Zalo Platform gửi POST event tới `https://your-domain/webhook`.

### Polling (Dev / Local)

```bash
python main.py --mode polling
```

Bot tự hỏi Zalo API mỗi vài giây để lấy tin mới.

---

## API Endpoints

| Method | Endpoint | Mô tả |
|---|---|---|
| `POST` | `/webhook` | Nhận event từ Zalo Platform |
| `GET` | `/health` | Health check |

---

## Zalo Event Schema

**Inbound (từ Zalo → service):**
```json
{
  "event_name": "user_send_text",
  "sender": { "id": "zalo_user_abc123" },
  "message": { "text": "Tư vấn sữa cho bé" },
  "timestamp": 1741879550000
}
```

**Outbound (service → Zalo API):**
```json
{
  "recipient": { "user_id": "zalo_user_abc123" },
  "message": { "text": "Chào bạn! Bé mấy tháng tuổi ạ?" }
}
```

---

## Cấu Hình `.env`

```env
# Zalo OA
ZALO_BOT_TOKEN=your_zalo_oa_token
ZALO_BASE_URL=https://openapi.zalo.me

# Địa chỉ models-service
MODEL_SERVICE_URL=http://localhost:8000

# Webhook
WEBHOOK_SECRET_TOKEN=your_secret_8_256_chars
WEBHOOK_BASE_URL=https://your-public-domain   # Phải HTTPS

# Logging
LOG_LEVEL=INFO
BOT_LOG_PATH=logs/zalo.log
```

---

## Techstack

| Thư viện | Mục đích |
|---|---|
| `fastapi` | Webhook HTTP server |
| `httpx` | Async HTTP tới Zalo API + models-service |
| `pydantic` | Schema parsing event Zalo |

---

## Nguyên Tắc Code

- ❌ KHÔNG log access token Zalo — mask toàn bộ
- ❌ KHÔNG dùng `print()` — log structured với `user_id`, `event_type`
- ✅ Verify webhook signature trước khi xử lý event
- ✅ Respond 200 OK về Zalo ngay lập tức — xử lý AI async (background task)
- ✅ Log: `event_type`, `user_id`, `message_len`, `response_ms`

---

## Lưu Ý Quan Trọng

- Webhook URL **bắt buộc HTTPS** — dùng ngrok hoặc Cloudflare Tunnel khi dev
- `WEBHOOK_SECRET_TOKEN` nên 8-256 ký tự
- Rate limit Zalo: tránh gửi quá nhiều tin trong 1 giây cho cùng 1 user
