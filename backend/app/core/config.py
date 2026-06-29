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
    # Neon Auth: the project's auth base URL, e.g.
    # https://ep-xxx.neonauth.<region>.aws.neon.tech/neondb/auth
    # The JWKS endpoint is "{NEON_AUTH_URL}/.well-known/jwks.json" and the JWT
    # issuer is the origin of this URL (scheme + host).
    NEON_AUTH_URL: str = ""
    STORAGE_BACKEND: str = "local"
    DEV_STORAGE_TOKEN: str = "dev-storage"


settings = Settings()
