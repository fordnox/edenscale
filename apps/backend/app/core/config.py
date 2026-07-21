from pydantic import model_validator
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

    # Inbound email → document ingestion (the Cloudflare email-ingest Worker
    # for cc@<domain>). The Worker authenticates to /email-ingest/documents with
    # this shared secret in the ``X-Email-Ingest-Token`` header. Empty means the
    # feature is OFF — the endpoint returns 404 until an operator sets a token.
    EMAIL_INGEST_TOKEN: str = ""

    # AI letter drafting (see app/services/letter_drafting.py). The documents
    # library exposes a "Draft letter" action that sends a document to an LLM
    # (via OpenRouter) and saves the result as a Communication draft. OFF until
    # OPENROUTER_API_KEY is set — the endpoint returns 404 and the feature is
    # inert without it. OPENROUTER_MODEL is any OpenRouter slug (e.g.
    # anthropic/claude-sonnet-5) and can be overridden per environment.
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "anthropic/claude-opus-4.8"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

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

    # HMAC secret used to sign the upload grant appended to `upload_url`
    # (see app/routers/documents.py) so `PUT /documents/upload/{key}` can
    # verify the key was actually issued to the caller. Empty disables
    # verification — only acceptable in local dev; the validator below
    # refuses to start with an empty secret in a production-shaped config.
    UPLOAD_SIGNING_SECRET: str = ""

    @model_validator(mode="after")
    def _require_upload_signing_secret_in_production(self) -> "Settings":
        """Refuse to start in a production-shaped configuration (DEBUG is
        false and APP_DOMAIN is not localhost) with no upload signing
        secret — that would silently disable the upload-grant check in
        `PUT /documents/upload/{key}`. Local development keeps working with
        an empty secret; see the DEV_STORAGE_TOKEN validator this mirrors."""
        domain_host = self.APP_DOMAIN.strip().split(":", 1)[0].lower()
        is_local = self.DEBUG or domain_host in ("localhost", "127.0.0.1")
        if not is_local and not self.UPLOAD_SIGNING_SECRET.strip():
            raise ValueError(
                "UPLOAD_SIGNING_SECRET must be set in a production-shaped "
                "configuration (DEBUG=false and APP_DOMAIN is not localhost)."
            )
        return self

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
    def letter_drafting_enabled(self) -> bool:
        """Whether AI letter drafting is configured (an API key is present)."""
        return bool(self.OPENROUTER_API_KEY.strip())

    @property
    def superadmin_emails(self) -> frozenset[str]:
        """Normalized set parsed from ``SUPERADMIN_EMAIL`` (comma-separated)."""
        return frozenset(
            email.strip().lower()
            for email in self.SUPERADMIN_EMAIL.split(",")
            if email.strip()
        )


settings = Settings()
