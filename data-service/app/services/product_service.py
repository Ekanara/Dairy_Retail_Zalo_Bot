from __future__ import annotations

import time
import uuid
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.db.models import Product
from app.repositories.product_repo import product_repo
from app.schemas.product import ProductCreate, ProductListResponse, ProductRead, ProductUpdate

logger = get_logger(__name__)


class ProductService:
    """Business logic layer — logs every operation and delegates DB work
    to ProductRepository.  Does NOT own session lifecycle; callers inject
    a session via FastAPI's `Depends(get_session)` dependency."""

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def list_products(
        self,
        session: AsyncSession,
        *,
        page: int = 1,
        size: int = 20,
        brand: str | None = None,
        segment: str | None = None,
    ) -> ProductListResponse:
        t0 = time.monotonic()
        products, total = await product_repo.get_all(
            session, page=page, size=size, brand=brand, segment=segment
        )
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "Listed products",
            extra={
                "action": "list_products",
                "page": page,
                "size": size,
                "brand": brand,
                "segment": segment,
                "total": total,
                "latency_ms": latency_ms,
                "user_id": None,
            },
        )
        return ProductListResponse(
            items=[ProductRead.model_validate(p) for p in products],
            total=total,
            page=page,
            size=size,
        )

    async def get_product(
        self, session: AsyncSession, product_id: uuid.UUID
    ) -> Product | None:
        t0 = time.monotonic()
        product = await product_repo.get_by_id(session, product_id)
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "Fetched product by ID",
            extra={
                "action": "get_product",
                "product_id": str(product_id),
                "found": product is not None,
                "latency_ms": latency_ms,
                "user_id": None,
            },
        )
        return product

    async def get_in_stock(self, session: AsyncSession) -> Sequence[Product]:
        t0 = time.monotonic()
        products = await product_repo.get_in_stock(session)
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "Fetched in-stock products",
            extra={
                "action": "get_in_stock",
                "count": len(products),
                "latency_ms": latency_ms,
                "user_id": None,
            },
        )
        return products

    async def get_out_of_stock(self, session: AsyncSession) -> Sequence[Product]:
        t0 = time.monotonic()
        products = await product_repo.get_out_of_stock(session)
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "Fetched out-of-stock products",
            extra={
                "action": "get_out_of_stock",
                "count": len(products),
                "latency_ms": latency_ms,
                "user_id": None,
            },
        )
        return products

    async def search_keyword(
        self,
        session: AsyncSession,
        query: str,
        limit: int = 10,
    ) -> Sequence[Product]:
        t0 = time.monotonic()
        products = await product_repo.search_keyword(session, query, limit)
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "Keyword search executed",
            extra={
                "action": "search_keyword",
                "query": query,
                "limit": limit,
                "results": len(products),
                "latency_ms": latency_ms,
                "user_id": None,
            },
        )
        return products

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def create_product(
        self, session: AsyncSession, data: ProductCreate
    ) -> Product:
        t0 = time.monotonic()
        product = await product_repo.create(session, data)
        await session.commit()
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "Product created",
            extra={
                "action": "create_product",
                "product_id": str(product.product_id),
                "name": product.name,
                "brand": product.brand,
                "latency_ms": latency_ms,
                "user_id": None,
            },
        )
        return product

    async def update_product(
        self,
        session: AsyncSession,
        product_id: uuid.UUID,
        data: ProductUpdate,
    ) -> Product | None:
        t0 = time.monotonic()
        product = await product_repo.update(session, product_id, data)
        await session.commit()
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "Product updated",
            extra={
                "action": "update_product",
                "product_id": str(product_id),
                "found": product is not None,
                "latency_ms": latency_ms,
                "user_id": None,
            },
        )
        return product

    async def delete_product(
        self, session: AsyncSession, product_id: uuid.UUID
    ) -> bool:
        t0 = time.monotonic()
        deleted = await product_repo.delete(session, product_id)
        await session.commit()
        latency_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "Product soft-deleted",
            extra={
                "action": "delete_product",
                "product_id": str(product_id),
                "deleted": deleted,
                "latency_ms": latency_ms,
                "user_id": None,
            },
        )
        return deleted


product_service = ProductService()
