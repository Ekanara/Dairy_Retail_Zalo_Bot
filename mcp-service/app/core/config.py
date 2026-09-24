from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/magic_sale"

    EMBEDDING_MODEL_NAME: str = "gemma3:0.3b"
    EMBEDDING_BASE_URL: str = "http://localhost:11434/v1"
    EMBEDDING_API_KEY: str = "ollama"

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "Nhà Sữa"
    SMTP_FROM_EMAIL: str = ""
    EMAIL_FROM: str = ""
    EMAIL_ENABLED: bool = False

    # Bank (VietQR payment)
    BANK_BIN: str = "970407"  # Techcombank
    BANK_ACCOUNT_NO: str = ""
    BANK_ACCOUNT_NAME: str = ""
    VIETQR_TEMPLATE: str = "compact2"

    @property
    def email_from_header(self) -> str:
        if self.SMTP_FROM_NAME and self.SMTP_FROM_EMAIL:
            return f"{self.SMTP_FROM_NAME} <{self.SMTP_FROM_EMAIL}>"
        return self.EMAIL_FROM or f"{self.SMTP_FROM_NAME} <{self.SMTP_USER}>"

    PROMPT_SERVICE_URL: str = "http://localhost:8001"
    ORDER_SERVICE_URL: str = "http://localhost:8003"
    ZALO_SERVICE_URL: str = "http://localhost:8080"
    RAG_SERVICE_URL: str = "http://localhost:8006"

    LOG_LEVEL: str = "INFO"

    MCP_TRANSPORT: str = "http"
    MCP_PORT: int = 8004

    class Config:
        env_file = ".env"


settings = Settings()
