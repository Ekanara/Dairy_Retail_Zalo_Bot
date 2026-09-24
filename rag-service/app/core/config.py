"""
Core configuration for RAG service.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Gemini Embedding Configuration
    gemini_api_key: str
    gemini_api_embedding_url: str = "https://generativelanguage.googleapis.com/v1beta"
    embedding_model_name: str = "models/text-embedding-004"

    # Qdrant Configuration
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None
    qdrant_https: bool = False

    # TEI Reranker Configuration
    tei_reranker_url: str = "http://localhost:8005"
    reranker_model_name: str = "BAAI/bge-reranker-v2-m3"

    # Service Configuration
    service_name: str = "rag-service"
    service_port: int = 8006
    log_level: str = "INFO"

    # RAG Configuration
    default_top_k: int = 20
    default_top_n: int = 5
    rrf_k: int = 60
    mmr_lambda: float = 0.7

    # Vector Configuration
    dense_vector_size: int = 768
    sparse_vector_size: int = 30000


# Global settings instance
settings = Settings()
