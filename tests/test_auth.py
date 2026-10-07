import uuid
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import select

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.database import SessionLocal, init_db
from app.main import app
from app.models.user import User


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_password_hashing():
    raw_pass = "SuperSecret123!"
    hashed = hash_password(raw_pass)
    assert hashed != raw_pass
    assert not hashed.startswith(raw_pass)
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


@pytest.mark.asyncio
async def test_registration_success_and_duplicate():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unique_id = uuid.uuid4().hex[:8]
        email = f"user_{unique_id}@example.com"
        username = f"user_{unique_id}"
        password = "password123"

        # 1. Successful registration
        res = await client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "email": email,
                "password": password,
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["email"] == email
        assert data["username"] == username
        assert "password" not in data
        assert "password_hash" not in data
        assert "id" in data

        # Verify password is saved as bcrypt hash in DB, not plaintext
        async with SessionLocal() as db:
            user_stmt = select(User).where(User.email == email)
            user_res = await db.execute(user_stmt)
            user_db = user_res.scalar_one_or_none()
            assert user_db is not None
            assert user_db.password_hash != password
            assert verify_password(password, user_db.password_hash) is True

        # 2. Duplicate registration rejected
        res_dup = await client.post(
            "/api/v1/auth/register",
            json={
                "username": f"other_{unique_id}",
                "email": email,
                "password": "anotherpassword123",
            },
        )
        assert res_dup.status_code == 400
        dup_data = res_dup.json()
        assert dup_data["error_code"] == "USER_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_login_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unique_id = uuid.uuid4().hex[:8]
        email = f"login_{unique_id}@example.com"
        username = f"login_{unique_id}"
        password = "correct_password123"

        # Register user
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={"username": username, "email": email, "password": password},
        )
        assert reg_res.status_code == 201

        # 1. Successful login
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        assert "refresh_token" in token_data
        assert token_data["token_type"].lower() == "bearer"

        # 2. Wrong password rejected
        bad_pw_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "wrong_password123"},
        )
        assert bad_pw_res.status_code == 401
        assert bad_pw_res.json()["error_code"] == "INVALID_CREDENTIALS"
        assert "Invalid credentials" in bad_pw_res.json()["message"]

        # 3. Unknown email rejected
        bad_email_res = await client.post(
            "/api/v1/auth/login",
            json={"email": f"unknown_{unique_id}@example.com", "password": password},
        )
        assert bad_email_res.status_code == 401
        assert bad_email_res.json()["error_code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_access_token_claims_and_validations():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unique_id = uuid.uuid4().hex[:8]
        email = f"token_{unique_id}@example.com"
        username = f"token_{unique_id}"
        password = "password123"

        reg_res = await client.post(
            "/api/v1/auth/register",
            json={"username": username, "email": email, "password": password},
        )
        assert reg_res.status_code == 201
        user_id = reg_res.json()["id"]

        # 1. Valid access token accepted
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        access_token = login_res.json()["access_token"]
        refresh_token = login_res.json()["refresh_token"]

        me_res = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_res.status_code == 200
        assert me_res.json()["id"] == user_id
        assert me_res.json()["email"] == email

        # 2. Expired access token rejected
        expired_token = create_access_token(
            data={"sub": user_id, "role": "user"},
            expires_delta=timedelta(seconds=-10),
        )
        exp_res = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert exp_res.status_code == 401
        assert exp_res.json()["error_code"] == "INVALID_TOKEN"

        # 3. Invalid signature rejected
        fake_token = jwt.encode(
            {"sub": user_id, "role": "user", "type": "access"},
            "wrong-secret-key-12345",
            algorithm="HS256",
        )
        fake_res = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {fake_token}"},
        )
        assert fake_res.status_code == 401
        assert fake_res.json()["error_code"] == "INVALID_TOKEN"

        # 4. Missing required sub rejected
        no_sub_token = jwt.encode(
            {"role": "user", "type": "access"},
            settings.TOKEN_SECRET_KEY,
            algorithm="HS256",
        )
        no_sub_res = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {no_sub_token}"},
        )
        assert no_sub_res.status_code == 401
        assert no_sub_res.json()["error_code"] == "INVALID_TOKEN"

        # 5. Refresh token cannot be used as an access token
        refresh_as_access = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert refresh_as_access.status_code == 401
        assert refresh_as_access.json()["error_code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_protected_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unauthenticated request to /films rejected with 401
        unauth_res = await client.get("/api/v1/films")
        assert unauth_res.status_code == 401
        assert unauth_res.json()["error_code"] == "INVALID_TOKEN"

        # 2. Invalid token rejected with 401
        bad_token_res = await client.get(
            "/api/v1/films",
            headers={"Authorization": "Bearer not-a-valid-token"},
        )
        assert bad_token_res.status_code == 401

        # 3. Valid token succeeds
        unique_id = uuid.uuid4().hex[:8]
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "username": f"route_user_{unique_id}",
                "email": f"route_{unique_id}@example.com",
                "password": "password123",
            },
        )
        assert reg_res.status_code == 201
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": f"route_{unique_id}@example.com", "password": "password123"},
        )
        access_token = login_res.json()["access_token"]

        auth_res = await client.get(
            "/api/v1/films",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert auth_res.status_code == 200
        assert "data" in auth_res.json()


@pytest.mark.asyncio
async def test_refresh_token_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unique_id = uuid.uuid4().hex[:8]
        email = f"refresh_{unique_id}@example.com"
        username = f"refresh_{unique_id}"
        password = "password123"

        await client.post(
            "/api/v1/auth/register",
            json={"username": username, "email": email, "password": password},
        )
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        orig_access_token = login_res.json()["access_token"]
        refresh_token = login_res.json()["refresh_token"]

        # 1. Valid refresh token issues a new access token
        ref_res1 = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert ref_res1.status_code == 200
        new_token_data = ref_res1.json()
        assert "access_token" in new_token_data
        new_access_token = new_token_data["access_token"]

        # Verify new access token works
        test_new_token = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        assert test_new_token.status_code == 200
        assert test_new_token.json()["email"] == email

        # 2. Access token cannot be used as refresh token
        ref_res_access_as_ref = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": orig_access_token},
        )
        assert ref_res_access_as_ref.status_code == 401
        assert ref_res_access_as_ref.json()["error_code"] == "INVALID_REFRESH_TOKEN"

        # 3. Expired refresh token rejected
        expired_ref = create_refresh_token(
            data={"sub": str(uuid.uuid4())},
            expires_delta=timedelta(seconds=-10),
        )
        ref_res_exp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": expired_ref},
        )
        assert ref_res_exp.status_code == 401
        assert ref_res_exp.json()["error_code"] == "INVALID_REFRESH_TOKEN"

        # 4. Invalid signature refresh token rejected
        fake_refresh = jwt.encode(
            {"sub": str(uuid.uuid4()), "type": "refresh"},
            "wrong-key-secret",
            algorithm="HS256",
        )
        ref_res_fake = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": fake_refresh},
        )
        assert ref_res_fake.status_code == 401
        assert ref_res_fake.json()["error_code"] == "INVALID_REFRESH_TOKEN"

        # 5. Refresh token for non-existent user rejected
        non_existent_user_token = create_refresh_token(
            data={"sub": str(uuid.uuid4())},
        )
        ref_res_non_user = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": non_existent_user_token},
        )
        assert ref_res_non_user.status_code == 401
        assert ref_res_non_user.json()["error_code"] == "INVALID_REFRESH_TOKEN"
