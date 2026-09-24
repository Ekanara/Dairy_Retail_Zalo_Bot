# order-service — Order Management

## Tổng Quan

`order-service` quản lý toàn bộ vòng đời đơn hàng: tạo order, lưu lịch sử, theo dõi tồn kho sản phẩm. Tất cả dữ liệu lưu vào **PostgreSQL**. Service này là nguồn sự thật cho trạng thái đơn hàng và inventory.

---

## Kiến Trúc

```
order-service/
├── app/
│   ├── core/
│   │   ├── config.py          # DATABASE_URL, env vars
│   │   └── logger.py          # Structured logger
│   ├── db/
│   │   ├── database.py        # SQLAlchemy async engine + session
│   │   └── models.py          # ORM: Order, OrderItem, StockLedger
│   ├── schemas/
│   │   ├── order.py           # OrderCreate, OrderRead, OrderStatus
│   │   └── order_item.py      # OrderItemCreate, OrderItemRead
│   ├── repositories/
│   │   └── order_repo.py      # DB queries (async)
│   ├── services/
│   │   └── order_service.py   # Business logic: tạo order, trừ stock
│   └── api/
│       └── routes.py          # FastAPI router
├── docs/
│   └── README.md              # (file này)
├── .env
└── main.py
```

---

## Schema Database

### Bảng `orders`

| Column | Kiểu | Mô tả |
|---|---|---|
| `order_id` | UUID (PK) | ID đơn hàng duy nhất |
| `user_id` | VARCHAR | Zalo User ID của khách |
| `customer_name` | TEXT | Họ tên khách |
| `customer_email` | TEXT | Email khách (nhận xác nhận) |
| `customer_phone` | TEXT | Số điện thoại |
| `status` | ENUM | `pending`, `confirmed`, `cancelled`, `delivered` |
| `total_amount` | NUMERIC(14,0) | Tổng tiền (VND) |
| `created_at` | TIMESTAMPTZ | Thời điểm tạo |
| `updated_at` | TIMESTAMPTZ | Thời điểm cập nhật |

---

### Bảng `order_items`

| Column | Kiểu | Mô tả |
|---|---|---|
| `item_id` | UUID (PK) | ID item |
| `order_id` | UUID (FK → orders) | Tham chiếu đơn hàng |
| `product_id` | UUID (FK → products) | Tham chiếu sản phẩm |
| `product_name` | TEXT | Snapshot tên sản phẩm lúc đặt |
| `unit_price` | NUMERIC(12,0) | Giá lúc đặt |
| `quantity` | INTEGER | Số lượng |
| `subtotal` | NUMERIC(14,0) | `unit_price × quantity` |

---

### Bảng `stock_ledger` — Lịch Sử Tồn Kho

| Column | Kiểu | Mô tả |
|---|---|---|
| `ledger_id` | UUID (PK) | ID bút toán |
| `product_id` | UUID (FK → products) | Sản phẩm |
| `delta` | INTEGER | Thay đổi số lượng (âm = bán, dương = nhập) |
| `reason` | VARCHAR | `sale`, `restock`, `adjustment` |
| `reference_id` | UUID | order_id hoặc ref khác |
| `created_at` | TIMESTAMPTZ | Thời điểm |

---

## API Endpoints

| Method | Endpoint | Mô tả |
|---|---|---|
| `POST` | `/orders` | Tạo đơn hàng mới |
| `GET` | `/orders/{order_id}` | Chi tiết 1 đơn hàng |
| `GET` | `/orders/user/{user_id}` | Lịch sử đơn hàng của 1 user |
| `PATCH` | `/orders/{order_id}/status` | Cập nhật trạng thái đơn (confirm/cancel) |
| `GET` | `/orders` | Danh sách tất cả đơn (admin, phân trang) |

---

## Business Logic Quan Trọng

### Khi Tạo Order

```
1. Validate product_id tồn tại và còn hàng
2. INSERT orders + order_items trong 1 transaction
3. INSERT stock_ledger (delta = -quantity)
4. UPDATE products.stock_quantity = stock_quantity - quantity
5. Commit transaction
6. Return order_id cho mcp-service (để gửi email)
```

### Khi Cancel Order

```
1. UPDATE orders SET status = 'cancelled'
2. INSERT stock_ledger (delta = +quantity, reason = 'adjustment')
3. UPDATE products.stock_quantity = stock_quantity + quantity
4. Commit
```

---

## Techstack

| Thư viện | Mục đích |
|---|---|
| `fastapi` | REST API |
| `sqlalchemy[asyncio]` | ORM async |
| `asyncpg` | PostgreSQL driver |
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

- ❌ KHÔNG dùng `print()` — log mọi transaction với `order_id`
- ❌ KHÔNG tăng/giảm stock bên ngoài transaction DB
- ✅ ACID transaction: order + stock trong cùng 1 `async with session.begin()`
- ✅ Rollback tự động nếu có lỗi bất kỳ trong transaction
