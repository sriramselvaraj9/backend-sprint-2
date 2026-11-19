import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, NoReturn

import boto3
from botocore.exceptions import ClientError, ConnectTimeoutError, EndpointConnectionError, ReadTimeoutError
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

logger = logging.getLogger("secrets_manager")
DATABASE_SECRET_NAME = os.environ.get("DATABASE_SECRET_NAME", "")
JWT_SECRET_NAME = os.environ.get("JWT_SECRET_NAME", "")


class SecretsManagerError(RuntimeError):
    pass


class DatabaseSecret(BaseModel):
    password: str
    database: str
    username: str = Field(default_factory=lambda: os.environ.get("POSTGRES_USER", "postgres"))
    host: str = Field(default_factory=lambda: os.environ.get("POSTGRES_HOST") or os.environ.get("DB_HOST", "db"))
    port: int = Field(default_factory=lambda: int(os.environ.get("DB_PORT", "5432")))
    model_config = {"extra": "ignore"}

    @property
    def database_url(self) -> str:
        from sqlalchemy.engine import URL
        host = os.environ.get("POSTGRES_HOST") or os.environ.get("DB_HOST") or self.host
        port = int(os.environ.get("DB_PORT") or self.port)
        user = os.environ.get("POSTGRES_USER") or self.username
        return URL.create(
            "postgresql+asyncpg",
            username=user,
            password=self.password,
            host=host,
            port=port,
            database=self.database,
        ).render_as_string(hide_password=False)


class JWTSecret(BaseModel):
    secret_key: str
    model_config = {"populate_by_name": True, "extra": "ignore"}


class AppSecrets(BaseModel):
    database: DatabaseSecret
    jwt: JWTSecret


_cached_secrets: AppSecrets | None = None


def _fail(msg: str, exc: Exception | None = None) -> NoReturn:
    logger.error(f"[SECRETS] {msg}")
    raise SecretsManagerError(msg) from exc


def get_secrets_manager_client(
    endpoint_url: str | None = None,
    region_name: str | None = None,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
) -> Any:
    kwargs: dict[str, Any] = {}
    if region := (region_name or os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION")):
        kwargs["region_name"] = region
    if key := (aws_access_key_id or os.environ.get("AWS_ACCESS_KEY_ID")):
        kwargs["aws_access_key_id"] = key
    if secret := (aws_secret_access_key or os.environ.get("AWS_SECRET_ACCESS_KEY")):
        kwargs["aws_secret_access_key"] = secret
    if endpoint := (
        endpoint_url 
        or os.environ.get("AWS_ENDPOINT_URL")
        or os.environ.get("AWS_ENDPOINT_URL_SECRETSMANAGER")
        or os.environ.get("SECRETS_MANAGER_ENDPOINT_URL")
    ):
        if "host.docker.internal" in endpoint and not os.path.exists("/.dockerenv"):
            endpoint = endpoint.replace("host.docker.internal", "localhost")
        kwargs["endpoint_url"] = endpoint
    return boto3.client("secretsmanager", **kwargs)


def fetch_secret(secret_name: str, client: Any | None = None) -> dict[str, Any]:
    sm_client = client or get_secrets_manager_client()
    try:
        response = sm_client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        if code == "ResourceNotFoundException":
            _fail(f"Required secret '{secret_name}' was not found.", e)
        if code in ("AccessDeniedException", "UnauthorizedException"):
            _fail(f"Access denied while retrieving secret '{secret_name}'.", e)
        _fail(f"Secrets Manager client error while retrieving secret '{secret_name}': {code}", e)
    except EndpointConnectionError as e:
        _fail(f"Unable to connect to Secrets Manager while retrieving secret '{secret_name}'.", e)
    except (ConnectTimeoutError, ReadTimeoutError, TimeoutError) as e:
        _fail(f"Connection timed out while retrieving secret '{secret_name}' from Secrets Manager.", e)
    except Exception as e:
        _fail(f"Unexpected error while retrieving secret '{secret_name}': {type(e).__name__}", e)

    if (secret_string := response.get("SecretString")) is None:
        _fail(f"Secret '{secret_name}' does not contain a secret string.")
    try:
        payload = json.loads(secret_string)
    except json.JSONDecodeError as e:
        _fail(f"Secret '{secret_name}' does not contain valid JSON.", e)
    if not isinstance(payload, dict):
        _fail(f"Secret '{secret_name}' must be a JSON object.")
    return payload


def get_database_secret(client: Any | None = None) -> DatabaseSecret:
    try:
        return DatabaseSecret.model_validate(fetch_secret(DATABASE_SECRET_NAME, client))
    except ValidationError as e:
        _fail(f"Secret '{DATABASE_SECRET_NAME}' is missing required fields or has an invalid schema.", e)


def get_jwt_secret(client: Any | None = None) -> JWTSecret:
    try:
        return JWTSecret.model_validate(fetch_secret(JWT_SECRET_NAME, client))
    except ValidationError as e:
        _fail(f"Secret '{JWT_SECRET_NAME}' is missing required fields or has an invalid schema.", e)


def load_secrets(client: Any | None = None) -> AppSecrets:
    return AppSecrets(database=get_database_secret(client), jwt=get_jwt_secret(client))


def get_app_secrets(refresh: bool = False, client: Any | None = None) -> AppSecrets:
    global _cached_secrets
    if _cached_secrets is None or refresh:
        _cached_secrets = load_secrets(client)
    return _cached_secrets


def clear_secrets_cache() -> None:
    global _cached_secrets
    _cached_secrets = None


def validate_secrets(client: Any | None = None) -> AppSecrets:
    return get_app_secrets(refresh=True, client=client)


if __name__ == "__main__":
    try:
        validate_secrets()
        print("[PASS] Secrets Manager validation: all required secrets retrieved and valid.")
    except Exception as err:
        print(f"[FAIL] Secrets Manager validation failed: {err}", file=sys.stderr)
        sys.exit(1)


