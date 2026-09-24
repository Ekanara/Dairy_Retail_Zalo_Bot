"""
chat-service configuration.

Settings
--------
DATABASE_URL     : PostgreSQL connection string (asyncpg driver)
REDIS_URL        : Redis connection string
LOG_LEVEL        : Logging level (INFO, DEBUG, WARNING, ERROR)
CACHE_TTL        : Redis cache TTL in seconds (default 86400 = 24 hours)
DEFAULT_TOP_K    : Default number of messages to return (default 10)
SERVICE_PORT     : Service port (default 8007)
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5434/magic_sale"
    REDIS_URL: str = "redis://localhost:6379/0"
    LOG_LEVEL: str = "INFO"
    CACHE_TTL: int = 86400  # 24 hours
    DEFAULT_TOP_K: int = 10
    SERVICE_PORT: int = 8007

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
