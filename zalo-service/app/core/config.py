from pathlib import Path

from pydantic_settings import BaseSettings

# Resolve .env relative to this file's service root (zalo-service/)
_SERVICE_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    ZALO_BOT_TOKEN: str = ""
    ZALO_BASE_URL: str = "https://bot-api.zaloplatforms.com"
    MODEL_SERVICE_URL: str = "http://localhost:8000"
    WEBHOOK_SECRET_TOKEN: str = ""
    WEBHOOK_BASE_URL: str = "https://your-domain.ngrok.io"
    LOG_LEVEL: str = "INFO"
    BOT_LOG_PATH: str = "logs/zalo.log"
    TRACE_CHAT_CONTENT: bool = False
    REDIS_URL: str = "redis://localhost:6379/0"
    CHAT_SERVICE_URL: str = "http://localhost:8007"

    class Config:
        env_file = str(_SERVICE_ROOT / ".env")
        env_file_encoding = "utf-8"


settings = Settings()
