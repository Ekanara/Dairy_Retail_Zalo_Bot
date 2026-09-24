from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import CustomerSegment, CustomerAge, ProductOrigin


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    brand_id: uuid.UUID | None = None
    origin: ProductOrigin | None = None
    customer_segment: CustomerSegment | None = None
    customer_age: CustomerAge | None = None
    product_purpose: str | None = None
    how_use: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    stock_quantity: int = Field(default=100, ge=0)


# ---------------------------------------------------------------------------
# Read (full representation returned by the API)
# ---------------------------------------------------------------------------
class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    name: str
    brand_id: uuid.UUID | None
    brand_name: str | None = None
    origin: ProductOrigin | None
    customer_segment: CustomerSegment | None
    customer_age: CustomerAge | None
    product_purpose: str | None
    how_use: str | None
    price: Decimal | None
    stock_quantity: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Update (all fields optional — PATCH-style via PUT endpoint)
# ---------------------------------------------------------------------------
class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    brand_id: uuid.UUID | None = None
    origin: ProductOrigin | None = None
    customer_segment: CustomerSegment | None = None
    customer_age: CustomerAge | None = None
    product_purpose: str | None = None
    how_use: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    stock_quantity: int | None = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Paginated list response
# ---------------------------------------------------------------------------
class ProductListResponse(BaseModel):
    items: list[ProductRead]
    total: int
    page: int
    size: int
