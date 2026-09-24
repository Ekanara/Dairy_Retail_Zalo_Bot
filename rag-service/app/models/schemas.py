"""
Pydantic models for RAG service API.
"""
from typing import Any
from pydantic import BaseModel, Field


class EmbeddingRequest(BaseModel):
    """Request model for embedding generation."""
    text: str | list[str] = Field(..., description="Text or list of texts to embed")
    task_type: str = Field(default="RETRIEVAL_DOCUMENT", description="Task type for embedding")


class EmbeddingResponse(BaseModel):
    """Response model for embedding generation."""
    embeddings: list[list[float]]
    model: str
    usage: dict[str, int]


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""
    source: str = Field(..., description="Source document identifier")
    date: str | None = Field(None, description="Document date")
    lang: str | None = Field(None, description="Document language")
    chunk_index: int = Field(..., description="Chunk index in source document")
    total_chunks: int = Field(..., description="Total chunks in source document")
    extra: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class DocumentChunk(BaseModel):
    """Document chunk for ingestion."""
    id: str = Field(..., description="Unique chunk identifier")
    text: str = Field(..., description="Chunk text content")
    metadata: ChunkMetadata


class IngestionRequest(BaseModel):
    """Request model for document ingestion."""
    project_name: str = Field(..., description="Project/collection name")
    chunks: list[DocumentChunk] = Field(..., description="Document chunks to ingest")


class IngestionResponse(BaseModel):
    """Response model for document ingestion."""
    project_name: str
    chunks_ingested: int
    status: str


class SearchRequest(BaseModel):
    """Request model for RAG search."""
    project_name: str = Field(..., description="Project/collection name to search")
    query: str = Field(..., description="Search query")
    top_k: int | None = Field(None, description="Number of results before reranking")
    top_n: int | None = Field(None, description="Number of final results after reranking")
    filters: dict[str, Any] | None = Field(None, description="Metadata filters")
    use_reranker: bool = Field(default=True, description="Whether to use reranker")
    use_mmr: bool = Field(default=True, description="Whether to apply MMR diversity filter")


class SearchResult(BaseModel):
    """Single search result."""
    id: str
    text: str
    score: float
    metadata: dict[str, Any]


class SearchResponse(BaseModel):
    """Response model for RAG search."""
    project_name: str
    query: str
    results: list[SearchResult]
    total_results: int


class CollectionInfo(BaseModel):
    """Information about a collection."""
    name: str
    vectors_count: int
    indexed_vectors_count: int
    points_count: int
    segments_count: int
    status: str


class CollectionListResponse(BaseModel):
    """Response model for listing collections."""
    collections: list[CollectionInfo]


class CollectionCreateRequest(BaseModel):
    """Request model for creating a collection."""
    project_name: str = Field(..., description="Project/collection name")


class CollectionCreateResponse(BaseModel):
    """Response model for collection creation."""
    project_name: str
    status: str
    message: str


class CollectionDeleteResponse(BaseModel):
    """Response model for collection deletion."""
    project_name: str
    status: str
    message: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    qdrant_connected: bool
    reranker_connected: bool
