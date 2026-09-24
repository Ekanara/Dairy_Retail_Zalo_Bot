# data-service — Product Catalog CRUD

## Tổng Quan

`data-service` quản lý toàn bộ catalog sản phẩm sữa — được import từ CSV nghiên cứu và lưu vào **PostgreSQL**. Mỗi sản phẩm có `product_id` riêng và join sang bảng `orders` để kiểm tra tình trạng tồn kho real-time.

---

## Kiến Trúc

```
data-service/
├── app/
│   ├── core/
│   │   ├── config.py          # DB connection string, env vars
│   │   └── logger.py          # Structured logger
│   ├── db/
│   │   ├── database.py        # SQLAlchemy async engine + session
│   │   └── models.py          # ORM: Product, Stock
│   ├── schemas/
│   │   ├── product.py         # ProductCreate, ProductRead, ProductUpdate
│   │   └── stock.py           # StockRead
│   ├── repositories/
│   │   └── product_repo.py    # DB queries (async)
│   ├── services/
│   │   └── product_service.py # Business logic CRUD + stock check
│   └── api/
│       └── routes.py          # FastAPI router
├── docs/
│   └── README.md              # (file này)
├── .env
└── main.py
```

---

## Schema Database

### Bảng `products`

| Column | Kiểu | Mô tả |
|---|---|---|
| `product_id` | UUID (PK) | ID duy nhất mỗi sản phẩm |
| `name` | TEXT | Tên sản phẩm đầy đủ |
| `brand` | VARCHAR(100) | Thương hiệu sản phẩm |
| `origin` | VARCHAR(100) | Xuất xứ (Singapore, Ai-len...) |
| `customer_segment` | TEXT | Đối tượng dùng (trẻ 0-6th, người lớn...) |
| `product_purpose` | TEXT | Mô tả công dụng đầy đủ |
| `how_use` | TEXT | Hướng dẫn sử dụng |
| `price` | NUMERIC(12,0) | Giá bán (VND) |
| `stock_quantity` | INTEGER | Số lượng tồn kho hiện tại |
| `created_at` | TIMESTAMPTZ | Thời điểm tạo |
| `updated_at` | TIMESTAMPTZ | Thời điểm cập nhật cuối |

> 📁 **Nguồn dữ liệu:** `trash/data/csv/product_infomation.csv` — cần import script khi bootstrap.

---

### Quan Hệ với `order-service`

```
products (product_id) ←──── order_items (product_id FK)
                                   │
                              orders (order_id)
```

- `stock_quantity` giảm khi order được confirm
- Query "sản phẩm còn hàng": `SELECT * FROM products WHERE stock_quantity > 0`

---

## API Endpoints (CRUD)

| Method | Endpoint | Mô tả |
|---|---|---|
| `GET` | `/products` | Lấy danh sách sản phẩm (phân trang, filter brand/segment) |
| `GET` | `/products/{product_id}` | Chi tiết 1 sản phẩm |
| `POST` | `/products` | Tạo sản phẩm mới |
| `PUT` | `/products/{product_id}` | Cập nhật thông tin sản phẩm |
| `DELETE` | `/products/{product_id}` | Xoá sản phẩm (soft delete) |
| `GET` | `/products/in-stock` | Lấy danh sách sản phẩm còn hàng |
| `GET` | `/products/out-of-stock` | Lấy danh sách sản phẩm hết hàng |

---

## Techstack

| Thư viện | Mục đích |
|---|---|
| `fastapi` | REST API |
| `sqlalchemy[asyncio]` | ORM async |
| `asyncpg` | PostgreSQL async driver |
| `pydantic` | Schema validation |
| `alembic` | Database migrations |

---

## Cấu Hình `.env`

```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5433/magic_sale
LOG_LEVEL=INFO
```

---

## Import CSV Khi Bootstrap

```bash
# Script import dữ liệu từ CSV vào PostgreSQL
python app/scripts/import_products.py --csv trash/data/csv/product_infomation.csv
```

---

## Nguyên Tắc Code

- ❌ KHÔNG dùng `print()` — log structured với service name
- ❌ KHÔNG bắt `Exception` chung — bắt `asyncpg.exceptions.*` cụ thể
- ✅ Dùng `async def` toàn bộ repository và service layer
- ✅ Dùng `Alembic` migration để thay đổi schema
