"""
FastAPI routes for RAG service.
"""
from fastapi import APIRouter, HTTPException, status

from app.core import logger
from app.models import (
    CollectionCreateRequest,
    CollectionCreateResponse,
    CollectionDeleteResponse,
    CollectionListResponse,
    HealthResponse,
    IngestionRequest,
    IngestionResponse,
    SearchRequest,
    SearchResponse,
)
from app.repositories import qdrant_repository
from app.services import rag_service, reranker_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns:
        Health status of the service and dependencies
    """
    qdrant_healthy = await qdrant_repository.health_check()
    reranker_healthy = await reranker_service.health_check()

    return HealthResponse(
        status="healthy" if qdrant_healthy else "degraded",
        service="rag-service",
        qdrant_connected=qdrant_healthy,
        reranker_connected=reranker_healthy,
    )


@router.post("/collections", response_model=CollectionCreateResponse)
async def create_collection(request: CollectionCreateRequest):
    """
    Create a new collection (project).

    Args:
        request: Collection creation request with project name

    Returns:
        Collection creation response
    """
    try:
        success = await qdrant_repository.create_collection(request.project_name)

        if not success:
            return CollectionCreateResponse(
                project_name=request.project_name,
                status="exists",
                message="Collection already exists",
            )

        return CollectionCreateResponse(
            project_name=request.project_name,
            status="created",
            message="Collection created successfully",
        )

    except Exception as e:
        logger.error(
            "Failed to create collection",
            extra={"project": request.project_name, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create collection: {str(e)}",
        )


@router.get("/collections", response_model=CollectionListResponse)
async def list_collections():
    """
    List all collections.

    Returns:
        List of collections with their information
    """
    try:
        collections = await qdrant_repository.list_collections()

        return CollectionListResponse(
            collections=collections
        )

    except Exception as e:
        logger.error(
            "Failed to list collections",
            extra={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list collections: {str(e)}",
        )


@router.delete("/collections/{project_name}", response_model=CollectionDeleteResponse)
async def delete_collection(project_name: str):
    """
    Delete a collection.

    Args:
        project_name: Name of the collection to delete

    Returns:
        Collection deletion response
    """
    try:
        await qdrant_repository.delete_collection(project_name)

        return CollectionDeleteResponse(
            project_name=project_name,
            status="deleted",
            message="Collection deleted successfully",
        )

    except Exception as e:
        logger.error(
            "Failed to delete collection",
            extra={"project": project_name, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete collection: {str(e)}",
        )


@router.post("/ingest", response_model=IngestionResponse)
async def ingest_documents(request: IngestionRequest):
    """
    Ingest documents into a collection.

    Pipeline: chunk → embed (dense + sparse) → upsert to Qdrant

    Args:
        request: Ingestion request with project name and document chunks

    Returns:
        Ingestion response with status
    """
    try:
        result = await rag_service.ingest_documents(request)

        return IngestionResponse(**result)

    except Exception as e:
        logger.error(
            "Failed to ingest documents",
            extra={"project": request.project_name, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest documents: {str(e)}",
        )


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Search for documents in a collection.

    Pipeline:
    1. Embed query (dense + sparse)
    2. Hybrid search (dense + sparse + filter)
    3. Re-rank (RRF score fusion + TEI reranker)
    4. MMR filter (diversity)

    Args:
        request: Search request with query and parameters

    Returns:
        Search results
    """
    try:
        result = await rag_service.search(request)

        return SearchResponse(**result)

    except Exception as e:
        logger.error(
            "Failed to search",
            extra={"project": request.project_name, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search: {str(e)}",
        )
