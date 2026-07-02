from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    DEBUG: bool = False
    GENERATE_OPENAPI_DOCS: bool = False
    APP_DOMAIN: str = "example.com"
    APP_DOMAIN_URL: str = "http://localhost:3000"
    APP_DATA_PATH: str = "/tmp"
    APP_DATABASE_DSN: str = "sqlite:////tmp/database.db"
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3000"]
    REDIS_URL: str = "redis://localhost:6379"
    HANKO_API_URL: str = ""
    HANKO_API_KEY: str = ""
    HANKO_AUDIENCE: str = "localhost"
    STORAGE_BACKEND: str = "local"
    DEV_STORAGE_TOKEN: str = "dev-storage"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_STARTTLS: bool = True
    EMAIL_FROM: str = ""
    EMAIL_ENABLED: bool = False


settings = Settings()
