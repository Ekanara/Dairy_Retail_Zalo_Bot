# mcp-service — Multi-Tool MCP Server

## Tổng Quan

`mcp-service` là MCP server xây dựng bằng **FastMCP**, đóng vai trò như "tay chân" của AI agent. Agent gọi các tool này để tìm kiếm sản phẩm, thực hiện RAG, đặt/cập nhật đơn hàng, và quản lý hồ sơ cá nhân người dùng.

---

## Kiến Trúc

```
mcp-service/
├── app/
│   ├── core/
│   │   ├── config.py          # Env vars: DB, embedding model, email
│   │   └── logger.py          # Structured logger
│   ├── db/
│   │   └── database.py        # Async DB session (chia sẻ với data-service)
│   ├── tools/
│   │   ├── search_tool.py     # Tool: keyword search trong DB
│   │   ├── rag_tool.py        # Tool: semantic search (Gemma 0.3B embedding)
│   │   ├── order_tool.py      # Tool: tạo/cập nhật order + gửi email xác nhận
│   │   └── personal_tool.py   # Tool: update USER.md / SOUL.md / MEMORY.md
│   ├── services/
│   │   ├── embedding_service.py # OpenAI-compatible call tới Gemma 0.3B (GPU)
│   │   └── email_service.py     # Gửi email xác nhận đơn hàng
│   └── server.py              # FastMCP app + tool registration
├── docs/
│   └── README.md              # (file này)
├── .env
└── main.py
```

---

## 4 Tool Chính

### 1. `search_keyword` — Tìm Kiếm Theo Từ Khoá

Tìm sản phẩm trong PostgreSQL bằng full-text search / ILIKE.

```python
@mcp.tool()
async def search_keyword(query: str, limit: int = 5) -> list[ProductResult]:
    """Tìm kiếm sản phẩm theo từ khoá (tên, thương hiệu, đối tượng dùng)"""
```

**Ví dụ gọi:**
```json
{ "query": "sữa bé 6 tháng", "limit": 5 }
```

---

### 2. `rag_search` — Semantic Search (RAG)

Dùng **Gemma 3 0.3B** (chạy GPU, OpenAI-compatible endpoint) để embed câu hỏi rồi cosine search trong vector store.

```python
@mcp.tool()
async def rag_search(question: str, top_k: int = 3) -> list[RagResult]:
    """Semantic search sản phẩm phù hợp nhất với câu hỏi của người dùng"""
```

**Flow:**
```
câu hỏi → embedding (Gemma 0.3B GPU) → cosine similarity → top_k products
```

**Cấu hình embedding:**
```env
EMBEDDING_MODEL_NAME=gemma3:0.3b
EMBEDDING_BASE_URL=http://localhost:11434/v1   # Ollama hoặc LM Studio
EMBEDDING_API_KEY=ollama
```

---

### 3. `create_order` — Tạo/Cập Nhật Đơn Hàng + Email

Ghi đơn hàng vào PostgreSQL, trừ tồn kho, gửi email xác nhận bằng tiếng Việt.

```python
@mcp.tool()
async def create_order(
    user_id: str,
    product_id: str,
    quantity: int,
    customer_name: str,
    customer_email: str,
    customer_phone: str
) -> OrderConfirmation:
    """Tạo đơn hàng và gửi email xác nhận cho khách"""
```

**Email xác nhận gồm:**
- Tên sản phẩm
- Giá tiền
- Quà kèm theo (nếu có trong tên sản phẩm)
- Lời cảm ơn bằng tiếng Việt

**Template email:**
```
Chào [customer_name],

Cảm ơn bạn đã đặt hàng tại Dairy AI! 🎉

📦 Sản phẩm: [product_name]
💰 Giá: [price] VND
🎁 Quà kèm: [gift] (nếu có)

Chúng tôi sẽ liên hệ xác nhận trong vòng 24h.
Trân trọng, Dairy AI Team
```

---

### 4. `update_personal_profile` — Cập Nhật Hồ Sơ Người Dùng

Cập nhật 3 file Markdown per-user trong prompt-service DB: `USER.md`, `SOUL.md`, `MEMORY.md`.

```python
@mcp.tool()
async def update_personal_profile(
    user_id: str,
    file_name: Literal["USER.md", "SOUL.md", "MEMORY.md"],
    content: str,
    mode: Literal["append", "replace"] = "append"
) -> bool:
    """Cập nhật file cá nhân của user để AI hiểu rõ hơn về người dùng"""
```

---

## Techstack

| Thư viện | Mục đích |
|---|---|
| `fastmcp` | MCP server framework |
| `sqlalchemy[asyncio]` | Async DB access |
| `asyncpg` | PostgreSQL driver |
| `httpx` | Gọi Gemma embedding endpoint |
| `aiosmtplib` | Gửi email async |
| `pgvector` | Vector similarity search trong PostgreSQL |

---

## Cấu Hình `.env`

```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5433/magic_sale

# Embedding model (Gemma 0.3B GPU)
EMBEDDING_MODEL_NAME=gemma3:0.3b
EMBEDDING_BASE_URL=http://localhost:11434/v1
EMBEDDING_API_KEY=ollama

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=Dairy AI <your_email@gmail.com>

# prompt-service endpoint (để update personal files)
PROMPT_SERVICE_URL=http://localhost:8001

LOG_LEVEL=INFO
```

---

## Chạy MCP Server

```bash
cd mcp-service
source .venv/bin/activate
python main.py   # FastMCP server chạy trên stdio hoặc HTTP transport
```

---

## Nguyên Tắc Code

- ❌ KHÔNG dùng `print()` — log structured mọi tool call
- ❌ KHÔNG catch `Exception` rộng — log lỗi DB, HTTP, SMTP cụ thể
- ✅ Mỗi tool phải return **typed Pydantic model**
- ✅ Log: `tool_name`, `user_id`, `duration_ms`, `result_count`
