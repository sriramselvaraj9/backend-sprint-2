import os
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

from app.core.secrets import get_app_secrets

# Path to the .env file in the project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    Typed centralized application settings.
    Non-sensitive configuration is loaded from .env and environment variables.
    Sensitive credentials (database credentials, JWT signing secret) are dynamically
    loaded from AWS Secrets Manager (or local Floci) via app.core.secrets.
    """

    DATABASE_URL: str = ""
    TOKEN_SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    ALLOWED_CORS_ORIGINS: str
    API_VERSION: str
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 60

    # AWS Credentials & Region Configuration
    AWS_REGION: str | None = None
    AWS_DEFAULT_REGION: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None

    # Secrets Manager Configuration
    DATABASE_SECRET_NAME: str = ""
    JWT_SECRET_NAME: str = ""

    # S3 Storage Configuration
    S3_BUCKET_NAME: str = ""
    S3_DEFAULT_PREFIX: str = ""
    S3_ENDPOINT_URL: str | None = None
    AWS_ENDPOINT_URL: str | None = None

    # Presigned URL Configuration
    PRESIGNED_URL_EXPIRE_SECONDS: int = 900
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024
    ALLOWED_UPLOAD_CONTENT_TYPES: list[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "application/pdf",
        "text/plain",
        "video/mp4",
        "application/json",
        "application/zip",
        "application/octet-stream",
    ]

    # SQS Queue Configuration
    SQS_QUEUE_NAME: str = "review-events-queue"
    SQS_DLQ_NAME: str = "review-events-dlq"
    SQS_ENDPOINT_URL: str | None = None
    SQS_MAX_RECEIVE_COUNT: int = 3
    SQS_VISIBILITY_TIMEOUT: int = 30
    SQS_WAIT_TIME_SECONDS: int = 20
    SQS_MAX_NUMBER_OF_MESSAGES: int = 10

    # Worker Test & Simulation Configuration
    SIMULATE_HANDLER_FAILURE: bool = False

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_post_init(self, __context: Any) -> None:
        """
        Merge secrets from Secrets Manager into settings after environment variables are loaded.
        Constructs DATABASE_URL safely using SQLAlchemy URL.create().
        """
        super().model_post_init(__context)
        app_secrets = get_app_secrets()
        if app_secrets and app_secrets.jwt:
            self.TOKEN_SECRET_KEY = app_secrets.jwt.secret_key
        if app_secrets and app_secrets.database:
            effective_host = (  
                os.environ.get("POSTGRES_HOST")
                or os.environ.get("DB_HOST")
                or app_secrets.database.host
            )
            if effective_host == "db" and not os.path.exists("/.dockerenv"):
                effective_host = "localhost"
            effective_port = int(os.environ.get("DB_PORT") or app_secrets.database.port)
            url = URL.create(
                drivername="postgresql+asyncpg",
                username=app_secrets.database.username,
                password=app_secrets.database.password,
                host=effective_host,
                port=effective_port,
                database=app_secrets.database.database,
            )
            self.DATABASE_URL = url.render_as_string(hide_password=False)

        # Map Redis host when running outside Docker
        if "redis://redis" in self.REDIS_URL and not os.path.exists("/.dockerenv"):
            self.REDIS_URL = self.REDIS_URL.replace("redis://redis", "redis://localhost")

        # Resolve AWS Region fallback
        if not self.AWS_REGION:
            self.AWS_REGION = self.AWS_DEFAULT_REGION

        # Resolve Endpoint URLs (mapping Docker internal host for local development)
        s3_endpoint = self.S3_ENDPOINT_URL or self.AWS_ENDPOINT_URL
        if s3_endpoint and "host.docker.internal" in s3_endpoint and not os.path.exists("/.dockerenv"):
            s3_endpoint = s3_endpoint.replace("host.docker.internal", "localhost")
        self.S3_ENDPOINT_URL = s3_endpoint

        sqs_endpoint = self.SQS_ENDPOINT_URL or self.AWS_ENDPOINT_URL
        if sqs_endpoint and "host.docker.internal" in sqs_endpoint and not os.path.exists("/.dockerenv"):
            sqs_endpoint = sqs_endpoint.replace("host.docker.internal", "localhost")
        self.SQS_ENDPOINT_URL = sqs_endpoint

    @property
    def database_password(self) -> str:
        """Compatibility accessor for database password from Secrets Manager."""
        secrets = get_app_secrets()
        return secrets.database.password if (secrets and secrets.database) else ""

    @property
    def jwt_secret(self) -> str:
        """Compatibility accessor for JWT secret key from Secrets Manager."""
        return self.TOKEN_SECRET_KEY


# Single config object created once when the config module is imported
settings = Settings()  # type: ignore[call-arg]
