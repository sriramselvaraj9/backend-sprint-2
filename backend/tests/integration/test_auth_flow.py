"""
tests/integration/test_auth_flow.py

Phase Seven: Registration, Login, and Authenticated-Request Integration Tests.
Exercises the real HTTP endpoints, FastAPI dependencies, UserService, UserDAO,
password hashing, JWT token lifecycle, and SQLite database persistence.
"""
# Integration tests covering registration, database verification with bcrypt password hash validation, login, token shape verification, and authenticated profile access (GET /api/v1/me), plus authentication failure cases
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models.user import User


@pytest.mark.integration
class TestAuthFlowIntegration:
    """Integration tests verifying full user registration, login, and authenticated requests."""

    async def test_full_registration_login_and_authenticated_profile_flow(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """
        Execute full lifecycle:
        1. Register new user through POST /api/v1/auth/register.
        2. Verify 201 Created status and UserResponse payload.
        3. Verify user is persisted in SQLite database.
        4. Confirm password is stored as bcrypt hash, never plain text.
        5. Log in through POST /api/v1/auth/login.
        6. Verify 200 OK and TokenResponse (access_token, refresh_token, token_type='bearer').
        7. Send GET /api/v1/me using the access token in Authorization: Bearer <token>.
        8. Verify 200 OK and correct user profile data returned.
        """
        # Step 1: Submit registration request
        register_payload = {
            "username": "test_member",
            "email": "test_member@example.com",
            "password": "SecurePassword123!",
        }
        register_response = await client.post("/api/v1/auth/register", json=register_payload)

        # Step 2: Verify registration response
        assert register_response.status_code == 201
        registered_data = register_response.json()
        assert registered_data["username"] == "test_member"
        assert registered_data["email"] == "test_member@example.com"
        assert registered_data["role"] == "viewer"
        assert "id" in registered_data
        assert "created_at" in registered_data
        assert "password" not in registered_data
        assert "password_hash" not in registered_data

        user_id = registered_data["id"]

        # Step 3: Verify user persisted in SQLite database
        stmt = select(User).where(User.email == "test_member@example.com")
        result = await db_session.execute(stmt)
        persisted_user = result.scalar_one_or_none()
        assert persisted_user is not None
        assert str(persisted_user.id) == user_id
        assert persisted_user.username == "test_member"

        # Step 4: Confirm password is cryptographically hashed with bcrypt
        assert persisted_user.password_hash != "SecurePassword123!"
        assert persisted_user.password_hash.startswith(("$2b$", "$2a$"))
        assert verify_password("SecurePassword123!", persisted_user.password_hash) is True
        assert verify_password("WrongPassword!", persisted_user.password_hash) is False

        # Step 5: Submit login request
        login_payload = {
            "email": "test_member@example.com",
            "password": "SecurePassword123!",
        }
        login_response = await client.post("/api/v1/auth/login", json=login_payload)

        # Step 6 & 7: Verify login response structure
        assert login_response.status_code == 200
        token_data = login_response.json()
        assert "access_token" in token_data
        assert "refresh_token" in token_data
        assert token_data["token_type"].lower() == "bearer"
        access_token = token_data["access_token"]
        assert isinstance(access_token, str) and len(access_token) > 20

        # Step 8: Call protected endpoint using Authorization: Bearer <token>
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        me_response = await client.get("/api/v1/me", headers=auth_headers)

        # Step 9: Confirm authenticated profile response
        assert me_response.status_code == 200
        me_data = me_response.json()
        assert me_data["id"] == user_id
        assert me_data["username"] == "test_member"
        assert me_data["email"] == "test_member@example.com"
        assert me_data["role"] == "viewer"

    async def test_login_failure_with_wrong_password(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify login returns 401 Unauthorized on invalid credentials."""
        # First register valid user
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "valid_user",
                "email": "valid_user@example.com",
                "password": "CorrectPassword1!",
            },
        )

        # Attempt login with wrong password
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "valid_user@example.com",
                "password": "WrongPassword1!",
            },
        )
        assert response.status_code == 401
        data = response.json()
        assert data.get("error_code") == "InvalidCredentialsError" or "detail" in data

    async def test_login_failure_with_nonexistent_email(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify login returns 401 Unauthorized for unknown emails."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "AnyPassword1!",
            },
        )
        assert response.status_code == 401

    async def test_protected_endpoint_rejects_missing_token(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify protected endpoint returns 401 when Authorization header is absent."""
        response = await client.get("/api/v1/me")
        assert response.status_code == 401

    async def test_protected_endpoint_rejects_invalid_token(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify protected endpoint returns 401 when token is forged or malformed."""
        response = await client.get(
            "/api/v1/me",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert response.status_code == 401

    async def test_duplicate_registration_rejected(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify registering with duplicate email returns 400 Bad Request."""
        payload = {
            "username": "unique_one",
            "email": "duplicate@example.com",
            "password": "Password123!",
        }
        resp1 = await client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        # Second attempt with same email
        payload_dup = {
            "username": "unique_two",
            "email": "duplicate@example.com",
            "password": "Password123!",
        }
        resp2 = await client.post("/api/v1/auth/register", json=payload_dup)
        assert resp2.status_code == 400
        data = resp2.json()
        assert data.get("error_code") == "UserAlreadyExistsError" or "detail" in data
