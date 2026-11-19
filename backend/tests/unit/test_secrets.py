"""
backend/tests/unit/test_secrets.py

Unit tests for AWS Secrets Manager integration (Floci) verifying:
1. Valid secrets allow retrieval and startup to continue
2. Missing database secret raises descriptive error identifying secret name
3. Missing JWT secret raises descriptive error identifying secret name
4. Access denied identifies the inaccessible secret
5. Unavailable Floci endpoint produces a descriptive connection error
6. Connection timeout produces a descriptive timeout error
7. Invalid secret JSON is rejected without leaking secret values
8. Missing required secret fields are rejected by Pydantic validation
9. In-memory process caching avoids duplicate API requests
10. Settings integration merges secrets into centralized configuration
11. Pre-deployment validate_secrets entrypoint behaves correctly
"""

import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError, ConnectTimeoutError, EndpointConnectionError

from app.core.config import Settings
from app.core.secrets import (
    DATABASE_SECRET_NAME,
    JWT_SECRET_NAME,
    AppSecrets,
    DatabaseSecret,
    JWTSecret,
    SecretsManagerError,
    clear_secrets_cache,
    fetch_secret,
    get_app_secrets,
    get_database_secret,
    get_jwt_secret,
    load_secrets,
    validate_secrets,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_cache():
    """Ensure in-memory cache is clean before and after each test."""
    clear_secrets_cache()
    yield
    clear_secrets_cache()


def make_mock_client(
    db_payload: dict | str | None = None,
    jwt_payload: dict | str | None = None,
    side_effects: dict | None = None,
) -> MagicMock:
    """Helper to create a mocked boto3 Secrets Manager client."""
    mock = MagicMock()

    db_str = json.dumps(db_payload) if isinstance(db_payload, dict) else db_payload
    jwt_str = json.dumps(jwt_payload) if isinstance(jwt_payload, dict) else jwt_payload

    def _get_secret_value(SecretId: str):
        if side_effects and SecretId in side_effects:
            effect = side_effects[SecretId]
            if isinstance(effect, Exception):
                raise effect
            return effect

        if SecretId == DATABASE_SECRET_NAME and db_str is not None:
            return {"SecretString": db_str}
        elif SecretId == JWT_SECRET_NAME and jwt_str is not None:
            return {"SecretString": jwt_str}
        raise ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Secret not found"}},
            "GetSecretValue",
        )

    mock.get_secret_value.side_effect = _get_secret_value
    return mock


# ---------------------------------------------------------------------------
# 1. Valid Secrets Retrieval and Typed Pydantic Validation
# ---------------------------------------------------------------------------
class TestValidSecretsRetrieval:
    """Verify valid secrets allow retrieval and startup to continue."""

    def test_valid_secrets_allow_startup_to_continue(self):
        client = make_mock_client(
            db_payload={
                "username": "postgres",
                "password": "production-db-password",
                "host": "localhost",
                "port": 5432,
                "database": "film_review_db",
            },
            jwt_payload={"secret_key": "production-jwt-signing-key"},
        )

        secrets = load_secrets(client=client)

        assert isinstance(secrets, AppSecrets)
        assert secrets.database.username == "postgres"
        assert secrets.database.password == "production-db-password"
        assert secrets.database.port == 5432
        assert "production-db-password" in secrets.database.database_url
        assert secrets.jwt.secret_key == "production-jwt-signing-key"

    def test_get_database_secret_retrieves_only_database_secret(self):
        """Verify get_database_secret fetches only the database secret without touching JWT."""
        client = make_mock_client(
            db_payload={
                "username": "postgres",
                "password": "init-db-password",
                "host": "db",
                "port": 5432,
                "database": "film_review_db",
            },
            jwt_payload={"secret_key": "jwt-should-not-be-fetched"},
        )

        db_secret = get_database_secret(client=client)

        assert isinstance(db_secret, DatabaseSecret)
        assert db_secret.password == "init-db-password"
        assert db_secret.username == "postgres"
        assert client.get_secret_value.call_count == 1
        client.get_secret_value.assert_called_once_with(SecretId=DATABASE_SECRET_NAME)

    def test_get_jwt_secret_retrieves_only_jwt_secret(self):
        """Verify get_jwt_secret fetches only the JWT secret without touching database secret."""
        client = make_mock_client(
            db_payload={"username": "postgres", "password": "p", "host": "db", "port": 5432, "database": "db"},
            jwt_payload={"secret_key": "jwt-only-key"},
        )

        jwt_secret = get_jwt_secret(client=client)

        assert isinstance(jwt_secret, JWTSecret)
        assert jwt_secret.secret_key == "jwt-only-key"
        assert client.get_secret_value.call_count == 1
        client.get_secret_value.assert_called_once_with(SecretId=JWT_SECRET_NAME)


# ---------------------------------------------------------------------------
# 2. In-Memory Process Caching
# ---------------------------------------------------------------------------
class TestSecretsCaching:
    """Verify in-memory caching: secrets loaded once per process."""

    def test_in_memory_caching_avoids_repeated_api_calls(self):
        client = make_mock_client(
            db_payload={
                "username": "postgres",
                "password": "pwd",
                "host": "localhost",
                "port": 5432,
                "database": "film_review_db",
            },
            jwt_payload={"secret_key": "key"},
        )

        first_call = get_app_secrets(client=client)
        assert client.get_secret_value.call_count == 2

        second_call = get_app_secrets(client=client)
        assert second_call is first_call
        assert client.get_secret_value.call_count == 2  # No extra calls!


# ---------------------------------------------------------------------------
# 3. Descriptive Error Handling
# ---------------------------------------------------------------------------
class TestSecretsErrorHandling:
    """Verify descriptive error handling for all required failure modes."""

    def test_missing_database_secret_stops_pre_deployment(self):
        """Missing database secret raises ResourceNotFoundException identifying the secret."""
        client = make_mock_client(
            side_effects={
                DATABASE_SECRET_NAME: ClientError(
                    {"Error": {"Code": "ResourceNotFoundException"}},
                    "GetSecretValue",
                )
            }
        )

        with pytest.raises(SecretsManagerError) as exc_info:
            load_secrets(client=client)

        assert f"Required secret '{DATABASE_SECRET_NAME}' was not found." == str(exc_info.value)

    def test_missing_jwt_secret_stops_pre_deployment(self):
        """Missing JWT secret raises ResourceNotFoundException identifying the secret."""
        client = make_mock_client(
            db_payload={
                "username": "postgres",
                "password": "pwd",
                "host": "localhost",
                "port": 5432,
                "database": "film_review_db",
            },
            side_effects={
                JWT_SECRET_NAME: ClientError(
                    {"Error": {"Code": "ResourceNotFoundException"}},
                    "GetSecretValue",
                )
            },
        )

        with pytest.raises(SecretsManagerError) as exc_info:
            load_secrets(client=client)

        assert f"Required secret '{JWT_SECRET_NAME}' was not found." == str(exc_info.value)

    def test_access_denied_identifies_inaccessible_secret(self):
        """AccessDeniedException identifies the inaccessible secret without leaking credentials."""
        client = make_mock_client(
            db_payload={
                "username": "postgres",
                "password": "pwd",
                "host": "localhost",
                "port": 5432,
                "database": "film_review_db",
            },
            side_effects={
                JWT_SECRET_NAME: ClientError(
                    {"Error": {"Code": "AccessDeniedException"}},
                    "GetSecretValue",
                )
            },
        )

        with pytest.raises(SecretsManagerError) as exc_info:
            load_secrets(client=client)

        assert f"Access denied while retrieving secret '{JWT_SECRET_NAME}'." == str(exc_info.value)

    def test_unavailable_floci_endpoint_produces_descriptive_error(self):
        """EndpointConnectionError produces clear error when Floci endpoint is unavailable."""
        client = make_mock_client(
            side_effects={
                DATABASE_SECRET_NAME: EndpointConnectionError(endpoint_url="http://localhost:4566")
            }
        )

        with pytest.raises(SecretsManagerError) as exc_info:
            load_secrets(client=client)

        assert (
            f"Unable to connect to Secrets Manager while retrieving secret '{DATABASE_SECRET_NAME}'."
            == str(exc_info.value)
        )

    def test_connection_timeout_produces_descriptive_error(self):
        """ConnectTimeoutError produces clear error identifying secret name."""
        client = make_mock_client(
            side_effects={
                DATABASE_SECRET_NAME: ConnectTimeoutError(endpoint_url="http://localhost:4566")
            }
        )

        with pytest.raises(SecretsManagerError) as exc_info:
            load_secrets(client=client)

        assert (
            f"Connection timed out while retrieving secret '{DATABASE_SECRET_NAME}' from Secrets Manager."
            == str(exc_info.value)
        )

    def test_invalid_secret_json_is_rejected(self):
        """Malformed JSON is rejected without printing secret text."""
        malformed_raw = "{unquoted_key:secret_value}"
        client = make_mock_client(
            db_payload=malformed_raw,
            jwt_payload={"secret_key": "jwt"},
        )

        with pytest.raises(SecretsManagerError) as exc_info:
            load_secrets(client=client)

        err_msg = str(exc_info.value)
        assert f"Secret '{DATABASE_SECRET_NAME}' does not contain valid JSON." == err_msg
        assert "secret_value" not in err_msg

    def test_missing_required_secret_fields_are_rejected(self):
        """Secret payload missing mandatory database fields (password or database) is rejected."""
        client = make_mock_client(
            db_payload={"username": "postgres", "host": "localhost"},
            jwt_payload={"secret_key": "jwt"},
        )

        with pytest.raises(SecretsManagerError) as exc_info:
            load_secrets(client=client)

        assert (
            f"Secret '{DATABASE_SECRET_NAME}' is missing required fields or has an invalid schema."
            == str(exc_info.value)
        )

    def test_secret_with_only_database_and_password_succeeds_using_env_fallbacks(self):
        """Secret payload containing only database and password succeeds using environment defaults."""
        client = make_mock_client(
            db_payload={
                "password": "only-db-and-pwd",
                "database": "film_review_db",
            },
            jwt_payload={"secret_key": "jwt"},
        )

        secrets = load_secrets(client=client)
        assert secrets.database.password == "only-db-and-pwd"
        assert secrets.database.database == "film_review_db"
        assert secrets.database.username == "postgres"
        assert secrets.database.port == 5432
        assert "only-db-and-pwd" in secrets.database.database_url


# ---------------------------------------------------------------------------
# 4. Centralized Config Settings Integration
# ---------------------------------------------------------------------------
class TestConfigSettingsIntegration:
    """Verify centralized Settings merges secrets without reading plaintext credentials from .env."""

    def test_settings_merges_secrets_into_config(self, monkeypatch):
        monkeypatch.delenv("POSTGRES_HOST", raising=False)
        monkeypatch.delenv("DB_HOST", raising=False)
        test_db = DatabaseSecret(
            username="testuser",
            password="testpassword123",
            host="testhost",
            port=5432,
            database="testdb",
        )
        test_jwt = JWTSecret(secret_key="testjwtkey456")
        mock_secrets = AppSecrets(database=test_db, jwt=test_jwt)

        monkeypatch.setattr("app.core.config.get_app_secrets", lambda refresh=False: mock_secrets)

        settings = Settings(
            ACCESS_TOKEN_EXPIRE_MINUTES=30,
            REFRESH_TOKEN_EXPIRE_DAYS=7,
            ALLOWED_CORS_ORIGINS="http://localhost:3000",
            API_VERSION="v1",
        )

        assert settings.TOKEN_SECRET_KEY == "testjwtkey456"
        assert settings.jwt_secret == "testjwtkey456"
        assert settings.database_password == "testpassword123"
        assert "testpassword123" in settings.DATABASE_URL
        assert "testhost" in settings.DATABASE_URL

    def test_pre_deployment_validate_secrets_entrypoint(self):
        """Verify pre-deployment validation entrypoint."""
        client = make_mock_client(
            db_payload={
                "username": "postgres",
                "password": "p",
                "host": "localhost",
                "port": 5432,
                "database": "film_review_db",
            },
            jwt_payload={"secret_key": "k"},
        )
        result = validate_secrets(client=client)
        assert isinstance(result, AppSecrets)

