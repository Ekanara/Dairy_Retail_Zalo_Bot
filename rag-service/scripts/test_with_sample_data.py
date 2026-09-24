"""
Test RAG service with sample product data (no data-service needed).
"""
import asyncio
import httpx

# Sample products for testing
SAMPLE_PRODUCTS = [
    {
        "product_id": "test-001",
        "name": "Sữa Pediasure Complete 850g",
        "brand_name": "Abbott",
        "origin": "usa",
        "customer_segment": "children",
        "customer_age": "age_4y_12y",
        "product_purpose": "Sản phẩm dinh dưỡng chuyên biệt cho trẻ biếng ăn, chậm lớn. Giúp tăng cân khỏe mạnh, phát triển chiều cao tối ưu.",
        "how_use": "Pha 5 muỗng gạt ngang (43.5g) với 190ml nước ấm. Uống 2 ly mỗi ngày.",
        "price": 450000,
        "stock_quantity": 50
    },
    {
        "product_id": "test-002",
        "name": "Ensure Gold HMB Vani 850g",
        "brand_name": "Abbott",
        "origin": "usa",
        "customer_segment": "elderly",
        "customer_age": "age_60y_plus",
        "product_purpose": "Dinh dưỡng dành cho người lớn tuổi. Bổ sung HMB giúp duy trì khối cơ, tăng cường sức khỏe xương khớp.",
        "how_use": "Pha 6 muỗng (54.9g) với 240ml nước. Uống 1-2 ly mỗi ngày.",
        "price": 545000,
        "stock_quantity": 30
    },
    {
        "product_id": "test-003",
        "name": "Glucerna Vani 850g",
        "brand_name": "Abbott",
        "origin": "usa",
        "customer_segment": "diabetic",
        "customer_age": "all_ages",
        "product_purpose": "Sữa chuyên biệt cho người tiểu đường. Kiểm soát đường huyết, cung cấp dinh dưỡng cân bằng.",
        "how_use": "Pha 5 muỗng với 200ml nước. Thay thế 1-2 bữa hoặc bữa phụ.",
        "price": 580000,
        "stock_quantity": 25
    },
]

RAG_SERVICE_URL = "http://localhost:8006"
PROJECT_NAME = "test_products"


async def main():
    """Test RAG service with sample data."""
    async with httpx.AsyncClient(timeout=30.0) as client:

        print("=" * 60)
        print("Testing RAG Service with Sample Data")
        print("=" * 60)
        print()

        # Step 1: Create collection
        print("1. Creating test collection...")
        response = await client.post(
            f"{RAG_SERVICE_URL}/api/v1/collections",
            json={"project_name": PROJECT_NAME}
        )
        print(f"   Status: {response.status_code}")
        print(f"   {response.json()}")
        print()

        # Step 2: Prepare chunks
        print("2. Preparing product chunks...")
        from app.services.product_transformer import product_transformer

        all_chunks = []
        for product in SAMPLE_PRODUCTS:
            chunks = product_transformer.transform_product_to_chunks(product)
            all_chunks.extend(chunks)

        print(f"   Created {len(all_chunks)} chunks from {len(SAMPLE_PRODUCTS)} products")
        print()

        # Step 3: Ingest
        print("3. Ingesting chunks...")
        response = await client.post(
            f"{RAG_SERVICE_URL}/api/v1/ingest",
            json={
                "project_name": PROJECT_NAME,
                "chunks": all_chunks
            }
        )
        print(f"   Status: {response.status_code}")
        print(f"   {response.json()}")
        print()

        # Step 4: Test searches
        test_queries = [
            "sữa cho trẻ biếng ăn",
            "sản phẩm cho người tiểu đường",
            "dinh dưỡng người cao tuổi"
        ]

        for i, query in enumerate(test_queries, 1):
            print(f"4.{i}. Searching: '{query}'")
            response = await client.post(
                f"{RAG_SERVICE_URL}/api/v1/search",
                json={
                    "project_name": PROJECT_NAME,
                    "query": query,
                    "top_k": 10,
                    "top_n": 3,
                    "use_reranker": False,  # No GPU
                    "use_mmr": True
                }
            )

            results = response.json()
            print(f"   Found: {results['total_results']} results")

            for j, result in enumerate(results['results'], 1):
                meta = result['metadata']
                print(f"   {j}. [{result['score']:.4f}] {meta['product_name']}")
                print(f"      Brand: {meta['brand_name']}, Price: {meta.get('price', 'N/A'):,}đ")
                print(f"      Type: {meta['chunk_type']}")
            print()

        print("=" * 60)
        print("✓ All tests completed successfully!")
        print("=" * 60)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/home/chaos/Documents/chaos/magic-sale-ai/rag-service")
    asyncio.run(main())
