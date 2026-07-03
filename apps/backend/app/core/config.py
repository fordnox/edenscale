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
    # Email delivery is via Resend hosted templates (see
    # app/services/channels/email_channel.py). Delivery is OFF until
    # RESEND_API_KEY is set — without it the notification pipeline still writes
    # in-app rows and logs, but the email channel returns a failure and nothing
    # leaves the box.
    RESEND_API_KEY: str = ""
    NOTIFICATION_FROM_EMAIL: str = "notifications@updates.newtaven.com"


settings = Settings()
