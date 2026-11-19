"""
tests/integration/test_logout_redis.py

Integration tests for the logout endpoint verifying Redis refresh token deletion,
exact key generation, call count assertion, and logout response shape.
"""

from unittest.mock import AsyncMock

import pytest
import redis.asyncio as aioredis
from httpx import AsyncClient

from app import dependencies
from app.main import app as fastapi_app

pytestmark = pytest.mark.integration


class TestLogoutRedisDeletion:
    """Tests verifying Redis key deletion behavior on user logout."""

    async def test_logout_deletes_exact_refresh_token_key_once(
        self,
        client: AsyncClient,
        viewer_token: str,
    ) -> None:
        """
        Logout Endpoint — Redis Deletion Test:
        - Mock the Redis client using the project's existing dependency structure.
        - Execute the logout endpoint with valid test authentication data.
        - Verify that the correct refresh-token Redis key is deleted.
        - Assert the exact key passed to the deletion method.
        - Assert that the deletion method is called exactly once.
        - Verify the expected logout response.
        """
        # 1. Create a mocked asynchronous Redis client
        mock_redis = AsyncMock(spec=aioredis.Redis)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.delete = AsyncMock(return_value=1)

        # 2. Override the get_redis dependency on the FastAPI application
        fastapi_app.dependency_overrides[dependencies.get_redis] = lambda: mock_redis

        test_refresh_token = "valid_sample_refresh_token_xyz123"
        expected_redis_key = f"refresh_token:{test_refresh_token}"

        try:
            # 3. Execute the logout endpoint with valid test authentication and refresh token payload
            response = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={"refresh_token": test_refresh_token},
            )

            # 4. Verify the expected logout response status and JSON shape
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Successfully logged out"
            assert data["status"] == "success"

            # 5. Assert the deletion method was called exactly once
            assert mock_redis.delete.await_count == 1

            # 6. Assert the exact Redis key passed to the deletion method
            mock_redis.delete.assert_awaited_once_with(expected_redis_key)
        finally:
            # Clean up dependency override
            fastapi_app.dependency_overrides.pop(dependencies.get_redis, None)

    async def test_logout_alias_route_deletes_refresh_token(
        self,
        client: AsyncClient,
        viewer_token: str,
    ) -> None:
        """
        Verify that POST /logout (unprefixed alias route) also correctly triggers
        refresh token deletion from Redis.
        """
        mock_redis = AsyncMock(spec=aioredis.Redis)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.delete = AsyncMock(return_value=1)

        fastapi_app.dependency_overrides[dependencies.get_redis] = lambda: mock_redis

        test_refresh_token = "alias_route_refresh_token_456"
        expected_redis_key = f"refresh_token:{test_refresh_token}"

        try:
            response = await client.post(
                "/logout",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={"refresh_token": test_refresh_token},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            mock_redis.delete.assert_awaited_once_with(expected_redis_key)
        finally:
            fastapi_app.dependency_overrides.pop(dependencies.get_redis, None)

    async def test_logout_unauthenticated_request_rejected(
        self,
        client: AsyncClient,
    ) -> None:
        """
        Verify that attempting to logout without a valid access token returns 401 Unauthorized
        and does not trigger any Redis deletion operations.
        """
        mock_redis = AsyncMock(spec=aioredis.Redis)
        mock_redis.delete = AsyncMock(return_value=1)

        fastapi_app.dependency_overrides[dependencies.get_redis] = lambda: mock_redis

        try:
            response = await client.post(
                "/api/v1/auth/logout",
                json={"refresh_token": "some_token"},
            )

            assert response.status_code == 401
            mock_redis.delete.assert_not_awaited()
        finally:
            fastapi_app.dependency_overrides.pop(dependencies.get_redis, None)
