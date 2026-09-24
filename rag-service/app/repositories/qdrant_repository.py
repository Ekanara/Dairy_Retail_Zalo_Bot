"""
Qdrant repository for vector storage operations.
"""
from typing import Any
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    PointStruct,
    Filter,
    SearchRequest,
    NamedVector,
    NamedSparseVector,
)

from app.core import logger, settings


class QdrantRepository:
    """Repository for Qdrant vector database operations."""

    def __init__(self):
        """Initialize Qdrant client."""
        self.client = AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key,
            https=settings.qdrant_https,
        )
        logger.info(
            "Qdrant repository initialized",
            extra={"host": settings.qdrant_host, "port": settings.qdrant_port}
        )

    async def create_collection(self, collection_name: str) -> bool:
        """
        Create a new collection with hybrid vector configuration.

        Args:
            collection_name: Name of the collection to create

        Returns:
            True if collection created successfully
        """
        try:
            # Check if collection already exists
            collections = await self.client.get_collections()
            if collection_name in [c.name for c in collections.collections]:
                logger.warning(
                    "Collection already exists",
                    extra={"collection": collection_name}
                )
                return False

            # Create collection with dense + sparse vectors
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": VectorParams(
                        size=settings.dense_vector_size,
                        distance=Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(
                        index=SparseIndexParams(
                            on_disk=False,
                        )
                    )
                },
            )

            # Create payload index for metadata fields
            await self.client.create_payload_index(
                collection_name=collection_name,
                field_name="source",
                field_schema="keyword",
            )
            await self.client.create_payload_index(
                collection_name=collection_name,
                field_name="date",
                field_schema="keyword",
            )
            await self.client.create_payload_index(
                collection_name=collection_name,
                field_name="lang",
                field_schema="keyword",
            )

            logger.info(
                "Collection created successfully",
                extra={"collection": collection_name}
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to create collection",
                extra={"collection": collection_name, "error": str(e)}
            )
            raise

    async def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection.

        Args:
            collection_name: Name of the collection to delete

        Returns:
            True if collection deleted successfully
        """
        try:
            await self.client.delete_collection(collection_name=collection_name)
            logger.info(
                "Collection deleted successfully",
                extra={"collection": collection_name}
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to delete collection",
                extra={"collection": collection_name, "error": str(e)}
            )
            raise

    async def list_collections(self) -> list[dict[str, Any]]:
        """
        List all collections with their info.

        Returns:
            List of collection information dictionaries
        """
        try:
            collections = await self.client.get_collections()

            result = []
            for collection in collections.collections:
                info = await self.client.get_collection(collection_name=collection.name)
                result.append({
                    "name": collection.name,
                    "vectors_count": info.vectors_count or 0,
                    "indexed_vectors_count": info.indexed_vectors_count or 0,
                    "points_count": info.points_count or 0,
                    "segments_count": info.segments_count or 0,
                    "status": info.status.name,
                })

            logger.info("Collections listed", extra={"count": len(result)})
            return result

        except Exception as e:
            logger.error("Failed to list collections", extra={"error": str(e)})
            raise

    async def upsert_points(
        self,
        collection_name: str,
        points: list[dict[str, Any]]
    ) -> bool:
        """
        Upsert points into collection with hybrid vectors.

        Args:
            collection_name: Name of the collection
            points: List of point dictionaries with id, dense_vector, sparse_vector, payload

        Returns:
            True if upsert successful
        """
        try:
            # Convert to PointStruct format
            qdrant_points = []
            for point in points:
                qdrant_points.append(
                    PointStruct(
                        id=point["id"],
                        vector={
                            "dense": point["dense_vector"],
                            "sparse": point["sparse_vector"],
                        },
                        payload=point["payload"],
                    )
                )

            # Upsert points
            await self.client.upsert(
                collection_name=collection_name,
                points=qdrant_points,
            )

            logger.info(
                "Points upserted successfully",
                extra={"collection": collection_name, "count": len(points)}
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to upsert points",
                extra={"collection": collection_name, "error": str(e)}
            )
            raise

    async def hybrid_search(
        self,
        collection_name: str,
        dense_vector: list[float],
        sparse_vector: dict[str, Any],
        limit: int,
        query_filter: Filter | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform hybrid search with dense + sparse vectors.

        Args:
            collection_name: Name of the collection to search
            dense_vector: Dense query vector
            sparse_vector: Sparse query vector with indices and values
            limit: Number of results to return
            query_filter: Optional metadata filter

        Returns:
            List of search results with id, score, payload
        """
        try:
            # Perform dense search
            dense_results = await self.client.search(
                collection_name=collection_name,
                query_vector=NamedVector(
                    name="dense",
                    vector=dense_vector,
                ),
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )

            # Perform sparse search
            from qdrant_client.models import SparseVector
            sparse_results = await self.client.search(
                collection_name=collection_name,
                query_vector=NamedSparseVector(
                    name="sparse",
                    vector=SparseVector(
                        indices=sparse_vector["indices"],
                        values=sparse_vector["values"],
                    ),
                ),
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )

            # Combine results (return both for RRF fusion in service layer)
            search_results = []
            seen_ids = set()

            # Add dense results
            for result in dense_results:
                search_results.append({
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload,
                    "source": "dense",
                })
                seen_ids.add(result.id)

            # Add unique sparse results
            for result in sparse_results:
                if result.id not in seen_ids:
                    search_results.append({
                        "id": result.id,
                        "score": result.score,
                        "payload": result.payload,
                        "source": "sparse",
                    })
                    seen_ids.add(result.id)

            logger.info(
                "Hybrid search completed",
                extra={
                    "collection": collection_name,
                    "results_count": len(search_results),
                }
            )
            return search_results

        except Exception as e:
            logger.error(
                "Hybrid search failed",
                extra={"collection": collection_name, "error": str(e)}
            )
            raise

    async def health_check(self) -> bool:
        """
        Check if Qdrant is healthy.

        Returns:
            True if Qdrant is healthy
        """
        try:
            await self.client.get_collections()
            return True
        except Exception:
            return False


# Global Qdrant repository instance
qdrant_repository = QdrantRepository()
