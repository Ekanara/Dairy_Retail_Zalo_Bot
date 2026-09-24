"""
CSV → PostgreSQL import script for product catalog.

Usage:
    python -m app.scripts.import_products --csv trash/data/csv/product_infomation.csv

Options:
    --csv     Path to the CSV file (required)
    --batch   Commit every N rows (default: 50)
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import re
import sys
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

# Ensure project root is on sys.path when run with python -m
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.core.logger import get_logger
from app.db.database import AsyncSessionLocal
from app.repositories.product_repo import product_repo
from app.schemas.product import ProductCreate

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# CSV column → model field mapping
# ---------------------------------------------------------------------------
COLUMN_MAP: dict[str, str] = {
    "name": "name",
    "brand": "brand",
    "origin": "origin",
    "custommerSegment": "customer_segment",   # note typo in CSV header
    "productPurpose": "product_purpose",
    "howUse": "how_use",
    "price": "price",
}


def _parse_price(raw: str) -> int | None:
    """Strip currency symbols, dots, spaces — return integer VND or None."""
    if not raw or raw.strip() == "":
        return None
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def _map_row(row: dict[str, str]) -> dict:
    """Convert one CSV row dict to keyword args for ProductCreate."""
    mapped: dict = {}
    for csv_col, model_field in COLUMN_MAP.items():
        value = row.get(csv_col, "").strip() or None
        if model_field == "price" and value:
            mapped[model_field] = _parse_price(value)
        else:
            mapped[model_field] = value
    mapped.setdefault("stock_quantity", 100)
    return mapped


async def _import(csv_path: Path, batch_size: int) -> None:
    t0 = time.monotonic()
    imported = 0
    skipped = 0
    errors = 0

    if not csv_path.is_file():
        logger.error(
            "CSV file not found",
            extra={"path": str(csv_path), "action": "import_products"},
        )
        sys.exit(1)

    async with AsyncSessionLocal() as session:
        session: AsyncSession

        with csv_path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            batch: list[ProductCreate] = []

            for lineno, row in enumerate(reader, start=2):  # line 1 = header
                try:
                    mapped = _map_row(row)
                    if not mapped.get("name"):
                        logger.error(
                            "Skipping row with empty name",
                            extra={"lineno": lineno, "row": dict(row)},
                        )
                        skipped += 1
                        continue

                    # Duplicate check (name + brand)
                    already_exists = await product_repo.exists_by_name_and_brand(
                        session,
                        name=mapped["name"],
                        brand=mapped.get("brand"),
                    )
                    if already_exists:
                        logger.info(
                            "Skipping duplicate product",
                            extra={
                                "lineno": lineno,
                                "name": mapped["name"],
                                "brand": mapped.get("brand"),
                                "action": "import_products",
                            },
                        )
                        skipped += 1
                        continue

                    batch.append(ProductCreate(**mapped))

                    if len(batch) >= batch_size:
                        for item in batch:
                            await product_repo.create(session, item)
                        await session.commit()
                        imported += len(batch)
                        logger.info(
                            "Batch committed",
                            extra={
                                "batch_size": len(batch),
                                "total_imported_so_far": imported,
                                "action": "import_products",
                            },
                        )
                        batch = []

                except (ValueError, TypeError) as exc:
                    logger.error(
                        "Row parse error — skipping",
                        extra={
                            "lineno": lineno,
                            "error": str(exc),
                            "row": dict(row),
                            "action": "import_products",
                        },
                    )
                    errors += 1
                    continue

            # Flush remaining rows
            if batch:
                for item in batch:
                    await product_repo.create(session, item)
                await session.commit()
                imported += len(batch)

    latency_ms = round((time.monotonic() - t0) * 1000, 2)
    logger.info(
        "Import complete",
        extra={
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "latency_ms": latency_ms,
            "action": "import_products",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import products from CSV into PostgreSQL"
    )
    parser.add_argument(
        "--csv",
        required=True,
        type=Path,
        help="Path to product_infomation.csv",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=50,
        help="Commit every N rows (default: 50)",
    )
    args = parser.parse_args()
    asyncio.run(_import(args.csv, args.batch))


if __name__ == "__main__":
    main()
