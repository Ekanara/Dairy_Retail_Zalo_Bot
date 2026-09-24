from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ──────────────────────────────────────────────────────────────
# Item-level schemas
# ──────────────────────────────────────────────────────────────

class OrderItemCreate(BaseModel):
    product_id: uuid.UUID
    product_name: str = Field(..., min_length=1, max_length=500)
    unit_price: int = Field(..., gt=0, description="Giá tại thời điểm đặt (VND)")
    quantity: int = Field(..., gt=0, description="Số lượng sản phẩm")


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: uuid.UUID
    order_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    unit_price: int
    quantity: int
    subtotal: int


# ──────────────────────────────────────────────────────────────
# Order-level schemas
# ──────────────────────────────────────────────────────────────

class OrderCreate(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    customer_name: str = Field(..., min_length=1, max_length=500)
    customer_email: EmailStr
    customer_phone: str = Field(..., min_length=7, max_length=20)
    items: list[OrderItemCreate] = Field(..., min_length=1)

    @field_validator("customer_phone")
    @classmethod
    def phone_digits_only(cls, v: str) -> str:
        cleaned = v.replace(" ", "").replace("-", "").replace("+", "")
        if not cleaned.isdigit():
            raise ValueError("customer_phone must contain only digits (and optional +, -, spaces)")
        return v


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: uuid.UUID
    user_id: str
    customer_name: str
    customer_email: str
    customer_phone: str
    status: str
    total_amount: int
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead] = []


class OrderStatusUpdate(BaseModel):
    status: Literal["confirmed", "cancelled", "delivered"]


# ──────────────────────────────────────────────────────────────
# Paginated list response
# ──────────────────────────────────────────────────────────────

class OrderListResponse(BaseModel):
    items: list[OrderRead]
    total: int
    page: int
    size: int
