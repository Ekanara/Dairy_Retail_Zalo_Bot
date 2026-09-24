"""
Test product search in RAG service.

This script demonstrates searching for products using natural language queries.

Usage:
    python scripts/test_product_search.py --query "sữa cho trẻ em"

Options:
    --query             Search query (default: "sữa cho trẻ em")
    --rag-service-url   URL of RAG service API (default: http://localhost:8006)
    --project-name      RAG collection name (default: magic_sale_products)
    --top-n             Number of results (default: 5)
"""
import argparse
import asyncio
import sys
from pathlib import Path

import httpx

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logger import logger


async def search_products(
    rag_service_url: str,
    project_name: str,
    query: str,
    top_n: int = 5
) -> None:
    """
    Search for products using RAG service.

    Args:
        rag_service_url: Base URL of RAG service
        project_name: Collection name
        query: Search query
        top_n: Number of results to return
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print(f"\n🔍 Searching for: '{query}'\n")

            response = await client.post(
                f"{rag_service_url}/api/v1/search",
                json={
                    "project_name": project_name,
                    "query": query,
                    "top_k": 20,
                    "top_n": top_n,
                    "use_reranker": True,
                    "use_mmr": True
                }
            )
            response.raise_for_status()
            results = response.json()

            total_results = results.get("total_results", 0)
            if total_results == 0:
                print("❌ No products found")
                return

            print(f"✅ Found {total_results} results:\n")
            print("=" * 80)

            for i, result in enumerate(results.get("results", []), 1):
                metadata = result.get("metadata", {})
                text = result.get("text", "")
                score = result.get("score", 0)

                print(f"\n{i}. [{score:.4f}] {metadata.get('product_name', 'N/A')}")
                print(f"   Brand: {metadata.get('brand_name', 'N/A')}")
                print(f"   Type: {metadata.get('chunk_type', 'N/A')}")

                if metadata.get('price'):
                    price = int(metadata['price'])
                    print(f"   Price: {price:,}đ")

                if metadata.get('customer_segment'):
                    print(f"   Segment: {metadata['customer_segment']}")

                if metadata.get('customer_age'):
                    print(f"   Age: {metadata['customer_age']}")

                if metadata.get('origin'):
                    print(f"   Origin: {metadata['origin']}")

                if metadata.get('stock_quantity') is not None:
                    stock = metadata['stock_quantity']
                    stock_status = "✓ In stock" if stock > 0 else "✗ Out of stock"
                    print(f"   Stock: {stock_status} ({stock} units)")

                print(f"\n   {text[:200]}...")

            print("\n" + "=" * 80)

            logger.info(
                "Search completed",
                extra={
                    "query": query,
                    "results_count": total_results,
                    "top_n": top_n
                }
            )

        except httpx.HTTPError as e:
            logger.error(
                "Search failed",
                extra={"error": str(e), "query": query}
            )
            print(f"\n❌ Search failed: {e}")
            raise


async def test_multiple_queries():
    """Run multiple test queries to demonstrate product search."""
    test_queries = [
        "sữa cho trẻ em",
        "vitamin cho người cao tuổi",
        "thuốc tiểu đường",
        "sản phẩm cho mẹ bầu",
        "thực phẩm chức năng cho phụ nữ"
    ]

    rag_service_url = "http://localhost:8006"
    project_name = "magic_sale_products"

    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"Query: {query}")
        print(f"{'='*80}")
        try:
            await search_products(rag_service_url, project_name, query, top_n=3)
            await asyncio.sleep(1)  # Small delay between queries
        except Exception as e:
            print(f"Error: {e}")
            continue


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test product search in RAG service"
    )
    parser.add_argument(
        "--query",
        default=None,
        help="Search query (if not provided, runs test suite)"
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
        "--top-n",
        type=int,
        default=5,
        help="Number of results (default: 5)"
    )

    args = parser.parse_args()

    try:
        if args.query:
            # Single query mode
            asyncio.run(search_products(
                rag_service_url=args.rag_service_url,
                project_name=args.project_name,
                query=args.query,
                top_n=args.top_n
            ))
        else:
            # Test suite mode
            print("\n🧪 Running test suite with multiple queries...\n")
            asyncio.run(test_multiple_queries())

    except KeyboardInterrupt:
        print("\n\nSearch cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error("Search test failed", extra={"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()
