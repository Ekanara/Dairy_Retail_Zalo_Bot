from __future__ import annotations

import uuid
from typing import Sequence

import asyncpg.exceptions
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.db.models import Product
from app.schemas.product import ProductCreate, ProductUpdate

logger = get_logger(__name__)


class ProductRepository:
    """All async DB operations for the products table.

    Every method expects a live *AsyncSession* and does NOT commit —
    committing is the caller's responsibility so operations can be
    composed into larger transactions (e.g. order-service stock decrement).
    """

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    async def get_all(
        self,
        session: AsyncSession,
        *,
        page: int = 1,
        size: int = 20,
        brand: str | None = None,
        segment: str | None = None,
    ) -> tuple[Sequence[Product], int]:
        """Return paginated products and the total count matching filters."""
        base_query = select(Product)

        if brand:
            base_query = base_query.where(
                Product.brand.ilike(f"%{brand}%")
            )
        if segment:
            base_query = base_query.where(
                Product.customer_segment.ilike(f"%{segment}%")
            )

        # Count before pagination
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await session.execute(count_query)
        total: int = total_result.scalar_one()

        # Apply pagination
        offset = (page - 1) * size
        paginated_query = base_query.offset(offset).limit(size).order_by(Product.created_at.desc())
        rows = await session.execute(paginated_query)
        products = rows.scalars().all()

        return products, total

    async def get_by_id(
        self, session: AsyncSession, product_id: uuid.UUID
    ) -> Product | None:
        """Fetch a single product by PK; returns None when not found."""
        result = await session.execute(
            select(Product).where(Product.product_id == product_id)
        )
        return result.scalar_one_or_none()

    async def get_in_stock(self, session: AsyncSession) -> Sequence[Product]:
        """All products with stock_quantity > 0."""
        result = await session.execute(
            select(Product)
            .where(Product.stock_quantity > 0)
            .order_by(Product.brand, Product.name)
        )
        return result.scalars().all()

    async def get_out_of_stock(self, session: AsyncSession) -> Sequence[Product]:
        """All products with stock_quantity = 0 (soft-deleted included)."""
        result = await session.execute(
            select(Product)
            .where(Product.stock_quantity == 0)
            .order_by(Product.brand, Product.name)
        )
        return result.scalars().all()

    async def search_keyword(
        self,
        session: AsyncSession,
        query: str,
        limit: int = 10,
    ) -> Sequence[Product]:
        """Full-text keyword search using ILIKE on name, brand, customer_segment."""
        pattern = f"%{query}%"
        result = await session.execute(
            select(Product)
            .where(
                Product.name.ilike(pattern)
                | Product.brand.ilike(pattern)
                | Product.customer_segment.ilike(pattern)
            )
            .limit(limit)
            .order_by(Product.name)
        )
        return result.scalars().all()

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    async def create(
        self, session: AsyncSession, data: ProductCreate
    ) -> Product:
        """Insert a new product row and return the hydrated ORM object."""
        try:
            product = Product(**data.model_dump())
            session.add(product)
            await session.flush()   # get server-generated defaults (UUID, timestamps)
            await session.refresh(product)
            return product
        except asyncpg.exceptions.UniqueViolationError as exc:
            logger.error(
                "Duplicate product insert blocked",
                extra={"error": str(exc), "action": "create_product"},
            )
            raise
        except asyncpg.exceptions.NotNullViolationError as exc:
            logger.error(
                "NOT NULL constraint violated on product insert",
                extra={"error": str(exc), "action": "create_product"},
            )
            raise

    async def update(
        self,
        session: AsyncSession,
        product_id: uuid.UUID,
        data: ProductUpdate,
    ) -> Product | None:
        """Update only the fields that were explicitly set in the payload."""
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return await self.get_by_id(session, product_id)

        try:
            await session.execute(
                update(Product)
                .where(Product.product_id == product_id)
                .values(**changes, updated_at=func.now())
                .execution_options(synchronize_session="fetch")
            )
            await session.flush()
            return await self.get_by_id(session, product_id)
        except asyncpg.exceptions.ForeignKeyViolationError as exc:
            logger.error(
                "FK violation on product update",
                extra={"product_id": str(product_id), "error": str(exc)},
            )
            raise

    async def delete(
        self, session: AsyncSession, product_id: uuid.UUID
    ) -> bool:
        """Soft delete: set stock_quantity = 0 so FK references remain intact."""
        try:
            result = await session.execute(
                update(Product)
                .where(Product.product_id == product_id)
                .values(stock_quantity=0, updated_at=func.now())
                .execution_options(synchronize_session="fetch")
            )
            await session.flush()
            return result.rowcount > 0
        except asyncpg.exceptions.ForeignKeyViolationError as exc:
            logger.error(
                "FK violation on product soft-delete",
                extra={"product_id": str(product_id), "error": str(exc)},
            )
            raise

    async def exists_by_name_and_brand(
        self,
        session: AsyncSession,
        name: str,
        brand: str | None,
    ) -> bool:
        """Check existence for duplicate-skip logic in the import script."""
        query = select(func.count()).select_from(Product).where(Product.name == name)
        if brand is not None:
            query = query.where(Product.brand == brand)
        result = await session.execute(query)
        return (result.scalar_one() or 0) > 0


product_repo = ProductRepository()
