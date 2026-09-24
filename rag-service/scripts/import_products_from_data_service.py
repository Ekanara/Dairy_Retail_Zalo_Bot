"""
Import products from data-service API into RAG service.

This script:
1. Fetches all products from data-service API
2. Transforms them into RAG-optimized text chunks
3. Ingests them into RAG service for semantic search

Usage:
    python scripts/import_products_from_data_service.py --data-service-url http://localhost:8002 --batch-size 10

Options:
    --data-service-url  URL of data-service API (default: http://localhost:8002)
    --rag-service-url   URL of RAG service API (default: http://localhost:8006)
    --project-name      RAG collection name (default: magic_sale_products)
    --batch-size        Number of products to process per batch (default: 10)
"""
import argparse
import asyncio
import sys
from pathlib import Path

import httpx

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logger import logger
from app.services.product_transformer import product_transformer


async def fetch_all_products(
    data_service_url: str,
    page_size: int = 100
) -> list[dict]:
    """
    Fetch all products from data-service API with pagination.

    Args:
        data_service_url: Base URL of data-service
        page_size: Number of products per page

    Returns:
        List of all product dictionaries
    """
    all_products = []
    page = 1

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            try:
                response = await client.get(
                    f"{data_service_url}/api/v1/products",
                    params={"page": page, "size": page_size}
                )
                response.raise_for_status()
                data = response.json()

                products = data.get("items", [])
                if not products:
                    break

                all_products.extend(products)
                logger.info(
                    "Fetched product page",
                    extra={
                        "page": page,
                        "products_in_page": len(products),
                        "total_so_far": len(all_products)
                    }
                )

                # Check if we've fetched all products
                total = data.get("total", 0)
                if len(all_products) >= total:
                    break

                page += 1

            except httpx.HTTPError as e:
                logger.error(
                    "Failed to fetch products from data-service",
                    extra={"error": str(e), "page": page}
                )
                raise

    logger.info("Finished fetching products", extra={"total_products": len(all_products)})
    return all_products


async def create_rag_collection(rag_service_url: str, project_name: str) -> bool:
    """
    Create RAG collection if it doesn't exist.

    Args:
        rag_service_url: Base URL of RAG service
        project_name: Name of the collection to create

    Returns:
        True if collection was created or already exists
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{rag_service_url}/api/v1/collections",
                json={"project_name": project_name}
            )
            response.raise_for_status()
            result = response.json()

            logger.info(
                "Collection status",
                extra={
                    "project_name": project_name,
                    "status": result.get("status"),
                    "message": result.get("message")
                }
            )
            return True

        except httpx.HTTPError as e:
            logger.error(
                "Failed to create collection",
                extra={"error": str(e), "project_name": project_name}
            )
            raise


async def ingest_product_batch(
    rag_service_url: str,
    project_name: str,
    chunks: list[dict]
) -> bool:
    """
    Ingest a batch of product chunks into RAG service.

    Args:
        rag_service_url: Base URL of RAG service
        project_name: Name of the collection
        chunks: List of chunk dictionaries

    Returns:
        True if ingestion succeeded
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{rag_service_url}/api/v1/ingest",
                json={
                    "project_name": project_name,
                    "chunks": chunks
                }
            )
            response.raise_for_status()
            result = response.json()

            logger.info(
                "Batch ingested successfully",
                extra={
                    "project_name": project_name,
                    "chunks_ingested": result.get("chunks_ingested"),
                    "status": result.get("status")
                }
            )
            return True

        except httpx.HTTPError as e:
            logger.error(
                "Failed to ingest batch",
                extra={"error": str(e), "chunks_count": len(chunks)}
            )
            raise


async def import_products(
    data_service_url: str,
    rag_service_url: str,
    project_name: str,
    batch_size: int
) -> None:
    """
    Main import function.

    Args:
        data_service_url: Base URL of data-service
        rag_service_url: Base URL of RAG service
        project_name: RAG collection name
        batch_size: Number of products per batch
    """
    import time
    t0 = time.time()

    logger.info(
        "Starting product import",
        extra={
            "data_service_url": data_service_url,
            "rag_service_url": rag_service_url,
            "project_name": project_name,
            "batch_size": batch_size
        }
    )

    # Step 1: Create RAG collection
    logger.info("Creating RAG collection...")
    await create_rag_collection(rag_service_url, project_name)

    # Step 2: Fetch all products from data-service
    logger.info("Fetching products from data-service...")
    products = await fetch_all_products(data_service_url)

    if not products:
        logger.warning("No products found in data-service")
        return

    # Step 3: Transform and ingest in batches
    logger.info("Transforming and ingesting products...")
    total_chunks = 0
    total_products = len(products)
    processed_products = 0

    current_batch = []

    for i, product in enumerate(products, 1):
        # Transform product to chunks
        chunks = product_transformer.transform_product_to_chunks(product)

        if not chunks:
            continue

        # Add chunks to current batch
        current_batch.extend(chunks)
        processed_products += 1

        # Ingest batch when it reaches batch_size products
        if processed_products % batch_size == 0 or i == total_products:
            if current_batch:
                logger.info(
                    "Ingesting batch",
                    extra={
                        "batch_num": (processed_products // batch_size) + 1,
                        "chunks_in_batch": len(current_batch),
                        "products_processed": processed_products,
                        "total_products": total_products
                    }
                )

                await ingest_product_batch(rag_service_url, project_name, current_batch)
                total_chunks += len(current_batch)
                current_batch = []

    elapsed = time.time() - t0

    logger.info(
        "Import completed successfully",
        extra={
            "total_products": total_products,
            "total_chunks": total_chunks,
            "elapsed_seconds": round(elapsed, 2),
            "chunks_per_second": round(total_chunks / elapsed, 2) if elapsed > 0 else 0
        }
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Import products from data-service into RAG service"
    )
    parser.add_argument(
        "--data-service-url",
        default="http://localhost:8002",
        help="Data service base URL (default: http://localhost:8002)"
    )
    parser.add_argument(
        "--rag-service-url",
        default="http://localhost:8006",
        help="RAG service base URL (default: http://localhost:8006)"
    )
    parser.add_argument(
        "--project-name",
        default="magic_sale_products",
        help="RAG collection name (default: magic_sale_products)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Products per batch (default: 10)"
    )

    args = parser.parse_args()

    try:
        asyncio.run(import_products(
            data_service_url=args.data_service_url,
            rag_service_url=args.rag_service_url,
            project_name=args.project_name,
            batch_size=args.batch_size
        ))
    except KeyboardInterrupt:
        logger.info("Import cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error("Import failed", extra={"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()
