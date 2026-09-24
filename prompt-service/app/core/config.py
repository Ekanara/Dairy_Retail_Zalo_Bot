from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/magic_sale"
    LOG_LEVEL: str = "INFO"
    PROMPT_ARCH_DIR: str = str(
        Path(__file__).parent.parent.parent / "prompt_architechture"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
