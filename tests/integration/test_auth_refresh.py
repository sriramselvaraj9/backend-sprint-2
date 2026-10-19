"""
tests/integration/test_auth_refresh.py

Integration tests for the token refresh flow (/api/v1/auth/refresh and UserService.refresh_access_token).
Verifies:
- Successful access token refresh using valid refresh token present in Redis.
- Rejection (401 / InvalidRefreshTokenError) when refresh token is revoked/absent from Redis.
- Rejection when refresh token is corrupted or has invalid JWT signature.
- Rejection when access token is incorrectly provided to refresh endpoint.
"""

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, create_refresh_token
from app.models.user import User

pytestmark = pytest.mark.integration


class TestAuthRefreshTokenFlow:
    """Tests verifying the token refresh endpoint and server-side Redis revocation checks."""

    async def test_refresh_token_success_issues_new_access_token(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Register a user, log in to receive access + refresh tokens (which persists token in Redis),
        and exchange refresh token for a newly minted access token via POST /api/v1/auth/refresh.
        """
        # 1. Register user
        reg_payload = {
            "username": "refresh_tester",
            "email": "refresh_tester@example.com",
            "password": "StrongPassword123!",
        }
        reg_resp = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_resp.status_code == 201

        # 2. Login to get refresh token stored in Redis
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "refresh_tester@example.com", "password": "StrongPassword123!"},
        )
        assert login_resp.status_code == 200
        tokens = login_resp.json()
        refresh_token = tokens["refresh_token"]
        assert refresh_token is not None

        # 3. Call POST /api/v1/auth/refresh with valid refresh token
        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_resp.status_code == 200
        new_token_data = refresh_resp.json()
        assert "access_token" in new_token_data
        assert isinstance(new_token_data["access_token"], str)
        assert len(new_token_data["access_token"]) > 20
        assert new_token_data["token_type"] == "bearer"

        # 4. Confirm new access token can be used to access protected /api/v1/me endpoint
        me_resp = await client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {new_token_data['access_token']}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == "refresh_tester"

    async def test_refresh_token_rejected_when_not_in_redis_revoked(
        self,
        client: AsyncClient,
        viewer_user_db: User,
    ) -> None:
        """
        A validly signed JWT refresh token that was never stored in Redis (or was revoked/deleted)
        must be rejected with 401 Unauthorized and type InvalidRefreshTokenError.
        """
        # Generate valid signed refresh token that is NOT in Redis
        untracked_token = create_refresh_token(data={"sub": str(viewer_user_db.id)})

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": untracked_token},
        )
        assert response.status_code == 401
        payload = response.json()
        assert payload["type"] == "InvalidRefreshTokenError"
        assert "revoked" in payload["message"].lower() or "invalid" in payload["message"].lower()

    async def test_refresh_token_rejected_on_corrupted_jwt(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Malformed or forged refresh token strings must be rejected with 401 Unauthorized.
        """
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "malformed.jwt.token.string"},
        )
        assert response.status_code == 401
        payload = response.json()
        assert payload["type"] == "InvalidRefreshTokenError"
        assert "invalid or expired" in payload["message"].lower()

    async def test_refresh_token_rejected_when_access_token_provided(
        self,
        client: AsyncClient,
        viewer_user_db: User,
    ) -> None:
        """
        Submitting an access token (type='access') to /refresh must be rejected with
        InvalidRefreshTokenError (expected refresh token).
        """
        access_tok = create_access_token(data={"sub": str(viewer_user_db.id), "role": "viewer"})

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_tok},
        )
        assert response.status_code == 401
        payload = response.json()
        assert payload["type"] == "InvalidRefreshTokenError"
        assert "expected refresh token" in payload["message"].lower()
