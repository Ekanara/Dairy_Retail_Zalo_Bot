from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────────────
    MODEL_NAME: str = "gpt-4.1-mini"
    MODEL_TEMPERATURE: float = 0.2
    API_KEY: str
    BASE_URL: str = "https://api.openai.com/v1"

    # ── Upstream services ────────────────────────────────────────────
    PROMPT_SERVICE_URL: str = "http://localhost:8001"
    MCP_SERVICE_URL: str = "http://localhost:8004"
    CHAT_SERVICE_URL: str = "http://localhost:8007"
    MCP_ENABLED: bool = True
    CHAT_HISTORY_ENABLED: bool = True  # Enable auto-save/load from chat-service

    # ── AgentSkill ────────────────────────────────────────────────────
    AGENTSKILL_DIR: str = ""  # Override path to agentskill package; empty = auto-detect sibling

    # ── Logging ──────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── HTTP timeouts (seconds) ───────────────────────────────────────
    PROMPT_SERVICE_TIMEOUT: float = 10.0
    CHAT_SERVICE_TIMEOUT: float = 5.0
    LLM_TIMEOUT: float = 60.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
