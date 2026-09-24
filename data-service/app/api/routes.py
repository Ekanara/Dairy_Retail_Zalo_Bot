from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.db.database import get_session
from app.schemas.product import (
    ProductCreate,
    ProductListResponse,
    ProductRead,
    ProductUpdate,
)
from app.services.product_service import product_service

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health", tags=["ops"])
async def health_check() -> dict:
    return {"status": "ok", "service": "data-service"}


# ---------------------------------------------------------------------------
# Static sub-paths MUST come before /{product_id} to avoid route shadowing
# ---------------------------------------------------------------------------


@router.get(
    "/products/in-stock",
    response_model=list[ProductRead],
    tags=["products"],
    summary="List all in-stock products (stock_quantity > 0)",
)
async def list_in_stock(
    session: AsyncSession = Depends(get_session),
) -> list[ProductRead]:
    products = await product_service.get_in_stock(session)
    return [ProductRead.model_validate(p) for p in products]


@router.get(
    "/products/out-of-stock",
    response_model=list[ProductRead],
    tags=["products"],
    summary="List all out-of-stock products (stock_quantity = 0)",
)
async def list_out_of_stock(
    session: AsyncSession = Depends(get_session),
) -> list[ProductRead]:
    products = await product_service.get_out_of_stock(session)
    return [ProductRead.model_validate(p) for p in products]


# ---------------------------------------------------------------------------
# Core CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/products",
    response_model=ProductListResponse,
    tags=["products"],
    summary="Paginated product list with optional brand/segment filters",
)
async def list_products(
    page: int = Query(default=1, ge=1, description="1-based page number"),
    size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    brand: str | None = Query(default=None, description="Filter by brand (ILIKE)"),
    segment: str | None = Query(default=None, description="Filter by customer segment (ILIKE)"),
    session: AsyncSession = Depends(get_session),
) -> ProductListResponse:
    return await product_service.list_products(
        session, page=page, size=size, brand=brand, segment=segment
    )


@router.get(
    "/products/{product_id}",
    response_model=ProductRead,
    tags=["products"],
    summary="Get a single product by UUID",
)
async def get_product(
    product_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ProductRead:
    product = await product_service.get_product(session, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    return ProductRead.model_validate(product)


@router.post(
    "/products",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    tags=["products"],
    summary="Create a new product",
)
async def create_product(
    payload: ProductCreate,
    session: AsyncSession = Depends(get_session),
) -> ProductRead:
    product = await product_service.create_product(session, payload)
    return ProductRead.model_validate(product)


@router.put(
    "/products/{product_id}",
    response_model=ProductRead,
    tags=["products"],
    summary="Update product fields (only supplied fields are changed)",
)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    session: AsyncSession = Depends(get_session),
) -> ProductRead:
    product = await product_service.update_product(session, product_id, payload)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    return ProductRead.model_validate(product)


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    tags=["products"],
    summary="Soft-delete a product (sets stock_quantity = 0)",
)
async def delete_product(
    product_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    deleted = await product_service.delete_product(session, product_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
