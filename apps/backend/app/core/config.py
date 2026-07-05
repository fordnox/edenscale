from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    DEBUG: bool = False
    GENERATE_OPENAPI_DOCS: bool = False
    APP_DOMAIN: str = "example.com"
    APP_DATA_PATH: str = "/tmp"
    APP_DATABASE_DSN: str = "sqlite:////tmp/database.db"
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3000"]
    REDIS_URL: str = "redis://localhost:6379"
    HANKO_API_URL: str = ""
    HANKO_API_KEY: str = ""
    HANKO_AUDIENCE: str = "localhost"
    # Superadmins are defined here, never in the database: a signed-in user
    # whose Hanko-verified email matches (case-insensitive) IS a superadmin.
    # Comma-separate to allow more than one; empty means no superadmins.
    SUPERADMIN_EMAIL: str = ""
    # Email delivery is via Resend hosted templates (see
    # app/services/channels/email_channel.py). Delivery is OFF until
    # RESEND_API_KEY is set — without it the notification pipeline still writes
    # in-app rows and logs, but the email channel returns a failure and nothing
    # leaves the box.
    RESEND_API_KEY: str = ""
    NOTIFICATION_FROM_EMAIL: str = "notifications@updates.newtaven.com"

    # S3/R2 storage settings
    STORAGE_BACKEND: str = "local"
    DEV_STORAGE_TOKEN: str = "dev-storage"
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET_NAME: str = "universal"
    S3_REGION: str = "auto"
    S3_PUBLIC_URL: str = ""
    S3_PREFIX: str = "taven"

    @property
    def app_domain_url(self) -> str:
        """Public base URL derived from ``APP_DOMAIN`` (no trailing slash) —
        used for links in outbound email. A localhost domain means a dev
        setup: plain http, defaulting to the manager dev port when the
        domain carries no port of its own."""
        domain = self.APP_DOMAIN.strip().rstrip("/")
        host = domain.split(":", 1)[0]
        if host in ("localhost", "127.0.0.1"):
            return f"http://{domain if ':' in domain else f'{domain}:3000'}"
        return f"https://{domain}"

    @property
    def superadmin_emails(self) -> frozenset[str]:
        """Normalized set parsed from ``SUPERADMIN_EMAIL`` (comma-separated)."""
        return frozenset(
            email.strip().lower()
            for email in self.SUPERADMIN_EMAIL.split(",")
            if email.strip()
        )


settings = Settings()
