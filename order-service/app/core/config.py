from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:55433/magic_sale"
    LOG_LEVEL: str = "INFO"

    # Email (SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "Nhà Sữa"
    SMTP_FROM_EMAIL: str = ""
    EMAIL_ENABLED: bool = False

    # SePay webhook (payment confirmation)
    SEPAY_API_KEY: str = ""
    ZALO_SERVICE_URL: str = "http://localhost:8080"

    class Config:
        env_file = ".env"


settings = Settings()
