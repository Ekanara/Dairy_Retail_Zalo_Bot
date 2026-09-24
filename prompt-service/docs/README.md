# prompt-service — Personalised Meta-Prompt Engine

## Tổng Quan

`prompt-service` là engine quản lý **meta prompt cá nhân hoá** cho từng người dùng. Mỗi user có bộ file Markdown riêng (`MEMORY.md`, `SOUL.md`, `USER.md`) được lưu trong PostgreSQL. Khi AI agent cần system prompt, nó gọi service này để lấy prompt được render đầy đủ theo template Jinja2.

---

## Kiến Trúc

```
prompt-service/
├── app/
│   ├── core/
│   │   ├── config.py           # DATABASE_URL, env vars
│   │   └── logger.py           # Structured logger
│   ├── db/
│   │   ├── database.py         # SQLAlchemy async engine
│   │   └── models.py           # ORM: UserPrompt
│   ├── schemas/
│   │   └── prompt.py           # PromptRead, PromptUpdate
│   ├── repositories/
│   │   └── prompt_repo.py      # CRUD per-user prompt files
│   ├── services/
│   │   └── prompt_service.py   # Render system_prompt.md với Jinja2
│   └── api/
│       └── routes.py           # FastAPI router
├── prompt_architechture/       # Template gốc cho AI agent
│   ├── system_prompt.md        # Master template (Jinja2 includes)
│   ├── AGENTS.md               # Định nghĩa agent behaviour
│   ├── IDENTITY.md             # Identity nhân vật AI
│   ├── SOUL.md                 # Cá tính, giọng điệu, phong cách
│   ├── USER.md                 # Hồ sơ người dùng
│   ├── MEMORY.md               # Bộ nhớ ngắn hạn / dài hạn
│   └── TOOLS.md                # Tool policies cho agent
├── docs/
│   └── README.md              # (file này)
├── .env
└── main.py
```

---

## Schema Database

### Bảng `user_prompts`

| Column | Kiểu | Mô tả |
|---|---|---|
| `id` | UUID (PK) | ID bản ghi |
| `user_id` | VARCHAR (UNIQUE) | Zalo User ID |
| `soul_md` | TEXT | Nội dung SOUL.md của user |
| `user_md` | TEXT | Nội dung USER.md của user |
| `memory_md` | TEXT | Nội dung MEMORY.md của user |
| `created_at` | TIMESTAMPTZ | Tạo lúc |
| `updated_at` | TIMESTAMPTZ | Cập nhật lúc |

> **Lần đầu user chat:** tự động tạo bản ghi với nội dung mặc định từ template.

---

## API Endpoints

| Method | Endpoint | Mô tả |
|---|---|---|
| `GET` | `/prompts/{user_id}` | Lấy system prompt đã render cho user |
| `GET` | `/prompts/{user_id}/raw` | Lấy raw 3 file MD của user |
| `PATCH` | `/prompts/{user_id}/soul` | Cập nhật SOUL.md |
| `PATCH` | `/prompts/{user_id}/user` | Cập nhật USER.md |
| `PATCH` | `/prompts/{user_id}/memory` | Cập nhật MEMORY.md |
| `POST` | `/prompts/{user_id}/init` | Khởi tạo prompt mặc định cho user mới |

---

## Cách Render System Prompt

```
GET /prompts/{user_id}
  ↓
Load user_prompts từ DB
  ↓
Load system_prompt.md (Jinja2 template)
  ↓
Render với context: {SOUL, USER, MEMORY, AGENTS, IDENTITY, TOOLS}
  ↓
Trả về rendered system prompt string
```

---

## Cấu Trúc `prompt_architechture/` — Anatomy of a Claude Prompt

Dựa trên pattern "The Anatomy of a Claude Prompt" (Ruben Hassid):

| File | Thành phần | Mô tả |
|---|---|---|
| `system_prompt.md` | **Task + Context Files** | Master template Jinja2, gom tất cả file con |
| `IDENTITY.md` | **Reference** | Tên nhân vật, vai trò, mô tả bản thân AI |
| `SOUL.md` | **Reference** | Tone giọng, phong cách, cá tính của AI |
| `AGENTS.md` | **Rules** | Luật hành xử, safety rules, giới hạn |
| `TOOLS.md` | **Context Files** | Tool nào được dùng và cách dùng |
| `USER.md` | **Context Files** | Hồ sơ khách hàng: tên, sở thích, lịch sử mua |
| `MEMORY.md` | **Context Files** | Bộ nhớ: pattern bán hàng, anti-pattern, tips |

---

## Techstack

| Thư viện | Mục đích |
|---|---|
| `fastapi` | REST API |
| `sqlalchemy[asyncio]` | ORM async |
| `asyncpg` | PostgreSQL driver |
| `jinja2` | Template rendering |
| `pydantic` | Schema validation |
| `alembic` | Migration |

---

## Cấu Hình `.env`

```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5433/magic_sale
LOG_LEVEL=INFO
```

---

## Nguyên Tắc Code

- ❌ KHÔNG xoá hoặc overwrite toàn bộ `<remind>` content nếu không được yêu cầu
- ❌ KHÔNG dùng `print()` — log structured với `user_id` và `file_name`
- ✅ Khi update file MD: dùng mode `append` hoặc `replace` tường minh
- ✅ Log mọi thay đổi: `user_id`, `file_name`, `mode`, `char_delta`
