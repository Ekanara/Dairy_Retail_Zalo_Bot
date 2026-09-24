"""
Example test script for RAG service.

This script demonstrates:
1. Creating a collection
2. Ingesting sample documents
3. Performing searches with different parameters
4. Testing filters
"""
import asyncio
import httpx


BASE_URL = "http://localhost:8006/api/v1"


async def test_rag_service():
    """Test RAG service functionality."""
    async with httpx.AsyncClient(timeout=30.0) as client:

        # 1. Health check
        print("=== Health Check ===")
        response = await client.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}\n")

        # 2. Create collection
        print("=== Create Collection ===")
        response = await client.post(
            f"{BASE_URL}/collections",
            json={"project_name": "test_project"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}\n")

        # 3. Ingest sample documents
        print("=== Ingest Documents ===")
        sample_chunks = [
            {
                "id": "doc1_chunk1",
                "text": "Python is a high-level, interpreted programming language known for its simplicity and readability. It supports multiple programming paradigms including procedural, object-oriented, and functional programming.",
                "metadata": {
                    "source": "python_intro.pdf",
                    "date": "2024-01-15",
                    "lang": "en",
                    "chunk_index": 0,
                    "total_chunks": 3,
                    "extra": {"topic": "programming", "page": 1}
                }
            },
            {
                "id": "doc1_chunk2",
                "text": "Python's extensive standard library provides tools for various tasks including file I/O, system calls, networking, and data manipulation. The language's dynamic typing and automatic memory management make it ideal for rapid development.",
                "metadata": {
                    "source": "python_intro.pdf",
                    "date": "2024-01-15",
                    "lang": "en",
                    "chunk_index": 1,
                    "total_chunks": 3,
                    "extra": {"topic": "programming", "page": 2}
                }
            },
            {
                "id": "doc2_chunk1",
                "text": "FastAPI is a modern, fast web framework for building APIs with Python 3.7+ based on standard Python type hints. It provides automatic API documentation and data validation using Pydantic models.",
                "metadata": {
                    "source": "fastapi_guide.pdf",
                    "date": "2024-02-01",
                    "lang": "en",
                    "chunk_index": 0,
                    "total_chunks": 2,
                    "extra": {"topic": "web_framework", "page": 1}
                }
            },
            {
                "id": "doc3_chunk1",
                "text": "Vector databases like Qdrant are designed to store and search high-dimensional vectors efficiently. They enable semantic search, recommendation systems, and RAG applications by finding similar vectors using algorithms like HNSW.",
                "metadata": {
                    "source": "vector_db_overview.pdf",
                    "date": "2024-03-10",
                    "lang": "en",
                    "chunk_index": 0,
                    "total_chunks": 1,
                    "extra": {"topic": "database", "page": 1}
                }
            },
            {
                "id": "doc4_chunk1",
                "text": "Machine learning models often require large amounts of training data and computational resources. Transfer learning techniques allow models to leverage pre-trained weights, reducing training time and data requirements.",
                "metadata": {
                    "source": "ml_basics.pdf",
                    "date": "2024-02-20",
                    "lang": "en",
                    "chunk_index": 0,
                    "total_chunks": 2,
                    "extra": {"topic": "machine_learning", "page": 1}
                }
            },
        ]

        response = await client.post(
            f"{BASE_URL}/ingest",
            json={
                "project_name": "test_project",
                "chunks": sample_chunks
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}\n")

        # Wait for indexing
        await asyncio.sleep(2)

        # 4. Search without reranker or MMR
        print("=== Search (Basic) ===")
        response = await client.post(
            f"{BASE_URL}/search",
            json={
                "project_name": "test_project",
                "query": "What is Python used for?",
                "top_k": 5,
                "top_n": 3,
                "use_reranker": False,
                "use_mmr": False
            }
        )
        print(f"Status: {response.status_code}")
        results = response.json()
        print(f"Found {results['total_results']} results:")
        for i, result in enumerate(results['results'], 1):
            print(f"{i}. [Score: {result['score']:.4f}] {result['text'][:100]}...")
        print()

        # 5. Search with reranker
        print("=== Search (With Reranker) ===")
        response = await client.post(
            f"{BASE_URL}/search",
            json={
                "project_name": "test_project",
                "query": "What is Python used for?",
                "top_k": 5,
                "top_n": 3,
                "use_reranker": True,
                "use_mmr": False
            }
        )
        print(f"Status: {response.status_code}")
        results = response.json()
        print(f"Found {results['total_results']} results:")
        for i, result in enumerate(results['results'], 1):
            print(f"{i}. [Score: {result['score']:.4f}] {result['text'][:100]}...")
        print()

        # 6. Search with reranker and MMR
        print("=== Search (With Reranker + MMR) ===")
        response = await client.post(
            f"{BASE_URL}/search",
            json={
                "project_name": "test_project",
                "query": "How do vector databases work?",
                "top_k": 5,
                "top_n": 3,
                "use_reranker": True,
                "use_mmr": True
            }
        )
        print(f"Status: {response.status_code}")
        results = response.json()
        print(f"Found {results['total_results']} results:")
        for i, result in enumerate(results['results'], 1):
            print(f"{i}. [Score: {result['score']:.4f}] {result['text'][:100]}...")
            print(f"   Source: {result['metadata']['source']}, Topic: {result['metadata']['extra']['topic']}")
        print()

        # 7. Search with filters
        print("=== Search (With Filter: topic=programming) ===")
        response = await client.post(
            f"{BASE_URL}/search",
            json={
                "project_name": "test_project",
                "query": "Tell me about programming",
                "top_k": 5,
                "top_n": 3,
                "use_reranker": True,
                "use_mmr": True,
                "filters": {
                    "extra.topic": "programming"
                }
            }
        )
        print(f"Status: {response.status_code}")
        results = response.json()
        print(f"Found {results['total_results']} results:")
        for i, result in enumerate(results['results'], 1):
            print(f"{i}. [Score: {result['score']:.4f}] {result['text'][:100]}...")
            print(f"   Topic: {result['metadata']['extra']['topic']}")
        print()

        # 8. List collections
        print("=== List Collections ===")
        response = await client.get(f"{BASE_URL}/collections")
        print(f"Status: {response.status_code}")
        collections = response.json()
        print(f"Collections: {len(collections['collections'])}")
        for coll in collections['collections']:
            print(f"  - {coll['name']}: {coll['points_count']} points, status: {coll['status']}")
        print()

        # 9. Delete collection (optional - uncomment to test)
        # print("=== Delete Collection ===")
        # response = await client.delete(f"{BASE_URL}/collections/test_project")
        # print(f"Status: {response.status_code}")
        # print(f"Response: {response.json()}\n")


if __name__ == "__main__":
    print("Testing RAG Service\n")
    asyncio.run(test_rag_service())
    print("\nTests completed!")
