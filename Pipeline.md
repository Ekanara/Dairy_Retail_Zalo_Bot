# Pipeline Chatbot Nhà Sữa - Magic Sale AI

## Tổng quan kiến trúc

```
Khách hàng (Zalo)
       │
       ▼
┌─────────────┐
│ zalo-service │  Port 8080 - Polling mode
│  (Gateway)   │  Nhận tin nhắn từ Zalo OA API
└──────┬──────┘
       │ POST /chat
       ▼
┌──────────────┐     GET /prompts/{user_id}     ┌────────────────┐
│models-service│ ◄──────────────────────────────► │ prompt-service  │
│  (AI Brain)  │     Port 8000                   │  Port 8001      │
│              │                                  │  System prompt   │
│  ReActAgent  │     GET/POST /chat/messages      │  SOUL/USER/     │
│  + SkillTool │ ◄──────────────────────────────► │  MEMORY.md      │
│  + Runtime   │     Port 8007                   └────────────────┘
│    Context   │ ◄──────────────────────────────► ┌────────────────┐
│              │                                  │  chat-service   │
│              │                                  │  Port 8007      │
│              │                                  │  Redis + PG     │
│              │                                  └────────────────┘
└──────┬──────┘
       │ MCP tools (streamable-http)
       ▼
┌──────────────┐
│ mcp-service  │  Port 8004 - FastMCP
│  (10 tools)  │
└──┬───┬───┬──┘
   │   │   │
   ▼   ▼   ▼
┌─────┐ ┌───────┐ ┌───────────┐
│data │ │order  │ │rag-service│
│svc  │ │svc    │ │Port 8006  │
│(DB) │ │Port   │ │Qdrant+TEI │
│     │ │8003   │ └───────────┘
└─────┘ └───┬───┘
            │
            ▼
      ┌───────────┐
      │ PostgreSQL │  Port 5434
      │  + Redis   │  Port 6379
      └───────────┘
```

---

## Quy trình bán hàng (5 Phase)

```
Khách nhắn "Hello"
       │
       ▼
┌──────────────────────────────────────────────────────┐
│  PHASE 1: MỞ ĐẦU (Opening)                          │
│  01-opening.md                                        │
│                                                       │
│  • Bot chào hỏi thân thiện                           │
│  • Hỏi TÊN khách (bắt buộc trước khi tư vấn)       │
│  • Hỏi: "Anh/chị muốn tìm sữa cho ai ạ?"           │
│  • Lưu tên vào USER.md                               │
└──────────┬───────────────────────────────────────────┘
           │ Khách trả lời: "cho bé 2 tuổi"
           ▼
┌──────────────────────────────────────────────────────┐
│  PHASE 2: KHAI THÁC NHU CẦU (Discovery)             │
│  02-discovery.md                                      │
│                                                       │
│  • Biết: cho ai + tuổi                               │
│  • Hỏi sức khỏe: "Bé có biếng ăn, hay ốm vặt       │
│    hay tình trạng gì không ạ?"                        │
│  • ⛔ KHÔNG được search sản phẩm ở phase này         │
│  • ⛔ KHÔNG được recommend sản phẩm                   │
└──────────┬───────────────────────────────────────────┘
           │ Khách trả lời: "bé biếng ăn, chậm lớn"
           ▼
┌──────────────────────────────────────────────────────┐
│  PHASE 3: TƯ VẤN SẢN PHẨM (Support)                │
│  03-support.md                                        │
│                                                       │
│  • Đủ 3 dữ kiện: ai + tuổi + sức khỏe              │
│  • ✅ GỌI search tools: rag_hybrid_search,           │
│    search_keyword, search_by_age                      │
│  • Giới thiệu sản phẩm CỤ THỂ: tên + giá           │
│  • Giải thích lợi ích phù hợp nhu cầu               │
│  • Brand mapping:                                     │
│    - Biếng ăn 1-10t → PediaSure                      │
│    - Chiều cao 2+  → Abbott Grow                     │
│    - Người lớn     → Ensure Gold                     │
│    - Tiểu đường    → Glucerna                        │
│    - Trẻ 0-12th    → Similac                         │
└──────────┬───────────────────────────────────────────┘
           │ Khách: "giá cao quá" / "để suy nghĩ"
           ▼
┌──────────────────────────────────────────────────────┐
│  PHASE 4: XỬ LÝ PHẢN ĐỐI (Objection Handling)      │
│  04-objection-handling.md                             │
│                                                       │
│  • Chê giá → so sánh giá/ngày, nhấn giá trị         │
│  • Do dự  → chia sẻ feedback khách cũ                │
│  • Đối thủ → so sánh ưu điểm Abbott                  │
│  • Tối đa 3 lần xử lý, không ép mua                 │
└──────────┬───────────────────────────────────────────┘
           │ Khách: "ok lấy đi" / "mua 1 hộp"
           ▼
┌──────────────────────────────────────────────────────┐
│  PHASE 5: CHỐT ĐƠN (Closing)                        │
│  05-closing.md                                        │
│                                                       │
│  ┌─── GỘP ĐƠN HÀNG ──────────────────────────────┐ │
│  │ 1. Xác nhận SP + số lượng                       │ │
│  │ 2. "Còn muốn thêm SP nào không?"               │ │
│  │    → Có: quay lại Phase 3 tư vấn thêm          │ │
│  │    → Không: tiếp tục                            │ │
│  │ 3. Tóm tắt giỏ hàng (tất cả SP + tổng tiền)   │ │
│  └─────────────────────────────────────────────────┘ │
│                                                       │
│  ┌─── THU THẬP THÔNG TIN ─────────────────────────┐ │
│  │ 4. Hỏi tên (nếu chưa có)                       │ │
│  │ 5. Hỏi EMAIL (⚠️ BẮT BUỘC trước khi tạo đơn)  │ │
│  │ 6. Hỏi SĐT (nếu chưa có)                      │ │
│  └─────────────────────────────────────────────────┘ │
│                                                       │
│  ┌─── TẠO ĐƠN ───────────────────────────────────┐ │
│  │ 7. create_order(product_names="SP1 x2, SP2 x1",│ │
│  │    customer_name, email, phone)                  │ │
│  │    → 1 ĐƠN DUY NHẤT cho tất cả SP              │ │
│  │    → 1 MÃ QR DUY NHẤT với tổng tiền gộp        │ │
│  │ 8. Gửi mã QR thanh toán qua Zalo               │ │
│  │ 9. Cảm ơn + hướng dẫn chuyển khoản             │ │
│  └─────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

---

## Quy trình thanh toán (SePay + VietQR)

```
┌──────────────────────────────────────────────────────┐
│                  TẠO ĐƠN HÀNG                        │
│                                                       │
│  mcp-service gọi order-service POST /orders           │
│  → Trừ stock (ACID transaction)                       │
│  → Tạo order status = "pending"                       │
│  → Sinh mã QR: VietQR (MB Bank 0935742434)           │
│  → Nội dung CK: DH{8 ký tự mã đơn}                  │
│  → ⚠️ KHÔNG gửi email ở bước này                     │
└──────────┬───────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│              GỬI MÃ QR QUA ZALO                      │
│                                                       │
│  mcp-service → POST zalo-service/internal/send-photo  │
│  Khách nhận ảnh QR + caption: "Mã QR đơn #XXXX"      │
│  Khách mở app ngân hàng, quét QR, chuyển khoản       │
└──────────┬───────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│           KHÁCH CHUYỂN KHOẢN                          │
│                                                       │
│  Khách → MB Bank (0935742434 VU ANH KHOI)            │
│  Nội dung: DH{mã đơn}                                │
│  Số tiền: tổng đơn hàng                              │
└──────────┬───────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│         SEPAY WEBHOOK → XÁC NHẬN THANH TOÁN          │
│                                                       │
│  SePay phát hiện giao dịch mới                        │
│  → POST /webhook/sepay tới order-service              │
│  → Trích mã đơn DH{8 hex} từ nội dung CK            │
│  → Tìm đơn hàng pending khớp mã                      │
│  → Kiểm tra số tiền ≥ tổng đơn                       │
│  → Cập nhật status: "pending" → "confirmed"           │
└──────────┬───────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│          THÔNG BÁO KHÁCH HÀNG                         │
│                                                       │
│  1. Gửi tin nhắn Zalo: "Cảm ơn bạn đã thanh toán    │
│     đơn #XXXX! Đơn hàng đang được xử lý."            │
│                                                       │
│  2. Gửi EMAIL xác nhận thanh toán thành công          │
│     (HTML template: tên SP, SL, giá, tổng tiền)       │
│     → CHỈ gửi email SAU KHI nhận đủ tiền             │
└──────────────────────────────────────────────────────┘
```

---

## Skill Runtime (AgentSkill)

```
┌─────────────────────────────────────────────────────┐
│              models-service                          │
│                                                      │
│  ┌───────────────────────────────────────────────┐  │
│  │           System Prompt                        │  │
│  │  prompt-service (SOUL/USER/MEMORY.md)          │  │
│  │  + SKILL.md (sales-conversion) auto-injected   │  │
│  └───────────────────────────────────────────────┘  │
│                     │                                │
│                     ▼                                │
│  ┌───────────────────────────────────────────────┐  │
│  │          ReActAgent (AgentScope)               │  │
│  │                                                │  │
│  │  Tools đăng ký:                                │  │
│  │  ├── Skill          (load skill khác)          │  │
│  │  ├── ReadSkillFile  (đọc resource/*.md)        │  │
│  │  ├── ListSkillFiles (liệt kê files)            │  │
│  │  ├── TodoWrite      (theo dõi task)            │  │
│  │  ├── view_text_file (legacy)                   │  │
│  │  └── 10 MCP tools (search, order, profile...)  │  │
│  └───────────────────────────────────────────────┘  │
│                     │                                │
│                     ▼                                │
│  ┌───────────────────────────────────────────────┐  │
│  │       RuntimeContextMemory                     │  │
│  │  (InMemoryMemory + system-reminder injection)  │  │
│  │                                                │  │
│  │  • Theo dõi active skill                       │  │
│  │  • Theo dõi loaded references                  │  │
│  │  • Theo dõi user request + next step           │  │
│  │  • Inject <system-reminder> trước mỗi LLM call│  │
│  └───────────────────────────────────────────────┘  │
│                                                      │
│  skills/                                             │
│  ├── sales-conversion/                               │
│  │   ├── SKILL.md (điều phối 5 phase)                │
│  │   └── resources/                                  │
│  │       ├── 01-opening.md                           │
│  │       ├── 02-discovery.md                         │
│  │       ├── 03-support.md                           │
│  │       ├── 04-objection-handling.md                │
│  │       └── 05-closing.md                           │
│  └── pediasure_chatbot/                              │
│      └── SKILL.md                                    │
└─────────────────────────────────────────────────────┘
```

---

## 10 MCP Tools

| Tool | Mô tả | Phase |
|------|--------|-------|
| `search_keyword` | Tìm SP theo từ khóa (ILIKE) | 03+ |
| `rag_search` | Tìm SP bằng semantic search | 03+ |
| `rag_hybrid_search` | Dense+Sparse+Rerank+MMR | 03+ |
| `search_by_segment` | Tìm theo đối tượng (trẻ em, người già...) | 03+ |
| `search_by_age` | Tìm theo độ tuổi | 03+ |
| `list_brands` | Liệt kê thương hiệu | Mọi phase |
| `search_by_brand` | Tìm theo brand | 03+ |
| `create_order` | Tạo đơn + QR (gộp nhiều SP) | 05 |
| `view_personal_profile` | Đọc SOUL/USER/MEMORY.md | Mọi turn |
| `edit_personal_profile` | Sửa USER.md (lưu tên, SĐT...) | Khi có info mới |

---

## Infra

```
┌─────────────────────────────┐
│       Docker Desktop         │
│                              │
│  ┌────────────────────────┐  │
│  │  PostgreSQL (pgvector)  │  │
│  │  Port 5434              │  │
│  │  DB: magic_sale         │  │
│  │  Tables: products,      │  │
│  │  brands, orders,        │  │
│  │  order_items, prompts,  │  │
│  │  chat_messages          │  │
│  └────────────────────────┘  │
│                              │
│  ┌────────────────────────┐  │
│  │  Redis                  │  │
│  │  Port 6379              │  │
│  │  Cache: chat history    │  │
│  │  TTL: 24h               │  │
│  └────────────────────────┘  │
└─────────────────────────────┘

┌─────────────────────────────┐
│    Cloudflare Tunnel         │
│    (cho SePay webhook)       │
│                              │
│    https://xxx.trycloudflare │
│    .com/webhook/sepay        │
│         │                    │
│         ▼                    │
│    order-service :8003       │
└─────────────────────────────┘
```
