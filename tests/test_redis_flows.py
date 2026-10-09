import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.redis import redis_client
from app.main import app


@pytest.fixture(autouse=True)
async def cleanup_redis():
    """Clean up any keys before and after tests."""
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


@pytest.mark.asyncio
async def test_film_list_caching_read_through():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login as viewer (charlie)
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "charlie@example.com", "password": "password123"},
        )
        assert login_resp.status_code == 200
        access_token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # 2. Verify Redis cache does not exist yet
        cached = await redis_client.get("films:list")
        assert cached is None

        # 3. First request: GET /api/v1/films (Cache MISS -> DB -> Store in Redis)
        resp1 = await client.get("/api/v1/films", headers=headers)
        assert resp1.status_code == 200
        films_data1 = resp1.json()["data"]
        assert len(films_data1) > 0

        # 4. Verify Redis now has the cached film list
        cached_str = await redis_client.get("films:list")
        assert cached_str is not None
        cached_list = json.loads(cached_str)
        assert len(cached_list) == len(films_data1)
        ttl = await redis_client.ttl("films:list")
        assert 0 < ttl <= 60

        # 5. Second request: GET /api/v1/films (Cache HIT -> Returns cached data without DB query)
        resp2 = await client.get("/api/v1/films", headers=headers)
        assert resp2.status_code == 200
        films_data2 = resp2.json()["data"]
        assert films_data2 == films_data1


@pytest.mark.asyncio
async def test_film_list_caching_with_filters():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "charlie@example.com", "password": "password123"},
        )
        access_token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Request Sci-Fi films
        resp_scifi = await client.get("/api/v1/films?genre=Sci-Fi", headers=headers)
        assert resp_scifi.status_code == 200

        # Verify specific filter key in Redis
        cached_scifi = await redis_client.get("films:list:genre=sci-fi")
        assert cached_scifi is not None

        # General list key is NOT yet created
        cached_general = await redis_client.get("films:list")
        assert cached_general is None

        # Now request Crime films
        resp_crime = await client.get("/api/v1/films?genre=Crime", headers=headers)
        assert resp_crime.status_code == 200

        cached_crime = await redis_client.get("films:list:genre=crime")
        assert cached_crime is not None
        assert cached_crime != cached_scifi


@pytest.mark.asyncio
async def test_year_range_filter_caching():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "charlie@example.com", "password": "password123"},
        )
        access_token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Filter by year range
        resp = await client.post(
            "/api/v1/films/filter/year-range",
            json={"start_year": 2000, "end_year": 2020},
            headers=headers,
        )
        assert resp.status_code == 200

        # Verify cache key was created for year range
        cached = await redis_client.get("films:list:min_year=2000:max_year=2020")
        assert cached is not None


@pytest.mark.asyncio
async def test_film_cache_invalidation_on_create_update_delete():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login as admin (alice)
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "alice@example.com", "password": "password123"},
        )
        assert login_resp.status_code == 200
        admin_token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Warm up the cache
        await client.get("/api/v1/films", headers=headers)
        await client.get("/api/v1/films?genre=Drama", headers=headers)
        assert await redis_client.get("films:list") is not None
        assert await redis_client.get("films:list:genre=drama") is not None

        # 1. CREATE film -> must invalidate all films:list* cache
        new_film_data = {
            "title": f"Test Film Redis {json.dumps({})}",
            "release_year": 2023,
            "genre": "Drama",
            "director": "Test Director",
        }
        create_resp = await client.post("/api/v1/films", json=new_film_data, headers=headers)
        assert create_resp.status_code == 200
        created_film = create_resp.json()
        film_id = created_film["id"]

        # Cache should now be cleared
        assert await redis_client.get("films:list") is None
        assert await redis_client.get("films:list:genre=drama") is None

        # Warm up cache again
        await client.get("/api/v1/films", headers=headers)
        assert await redis_client.get("films:list") is not None

        # 2. UPDATE film -> must invalidate all films:list* cache
        update_resp = await client.patch(f"/api/v1/films/{film_id}", headers=headers)
        assert update_resp.status_code == 200
        assert await redis_client.get("films:list") is None

        # Warm up cache again
        await client.get("/api/v1/films", headers=headers)
        assert await redis_client.get("films:list") is not None

        # 3. SOFT-DELETE film -> must invalidate all films:list* cache
        delete_resp = await client.delete(f"/api/v1/films/{film_id}", headers=headers)
        assert delete_resp.status_code == 200
        assert await redis_client.get("films:list") is None


@pytest.mark.asyncio
async def test_refresh_token_lifecycle_and_redis():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login -> creates tokens and stores refresh token in Redis with TTL
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "bob@example.com", "password": "password123"},
        )
        assert login_resp.status_code == 200
        tokens = login_resp.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        assert refresh_token is not None

        # Verify refresh token in Redis stores user ID
        stored_user_id = await redis_client.get(f"refresh_token:{refresh_token}")
        assert stored_user_id is not None

        # Verify TTL is set (approx 7 days = 604800s)
        ttl = await redis_client.ttl(f"refresh_token:{refresh_token}")
        assert 600000 <= ttl <= 7 * 86400

        # 2. Wait 1.1s so iat / exp timestamp changes for new token
        await asyncio.sleep(1.1)

        # Valid refresh request -> succeeds and returns new access token
        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_resp.status_code == 200
        new_tokens = refresh_resp.json()
        assert "access_token" in new_tokens
        new_access_token = new_tokens["access_token"]
        assert new_access_token != access_token


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "charlie@example.com", "password": "password123"},
        )
        tokens = login_resp.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        assert await redis_client.get(f"refresh_token:{refresh_token}") is not None

        # 2. Logout with access token (no explicit body needed; uses stored user mapping)
        logout_resp = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert logout_resp.status_code == 200
        assert logout_resp.json()["status"] == "success"

        # 3. Verify refresh token was deleted from Redis
        assert await redis_client.get(f"refresh_token:{refresh_token}") is None

        # 4. Attempt to use revoked refresh token -> must be rejected with 401
        failed_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert failed_refresh.status_code == 401
        assert failed_refresh.json()["error_code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.asyncio
async def test_logout_root_alias():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "alice@example.com", "password": "password123"},
        )
        tokens = login_resp.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        # Call top-level /logout
        logout_resp = await client.post(
            "/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"refresh_token": refresh_token},
        )
        assert logout_resp.status_code == 200
        assert await redis_client.get(f"refresh_token:{refresh_token}") is None


@pytest.mark.asyncio
async def test_preserved_rbac_and_profile_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Viewer login
        viewer_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "charlie@example.com", "password": "password123"},
        )
        viewer_token = viewer_login.json()["access_token"]
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        # Viewer can access GET /me
        me_resp = await client.get("/api/v1/me", headers=viewer_headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == "charlie_fan"
        assert me_resp.json()["role"] == "viewer"

        # Viewer is forbidden from GET /api/v1/admin/stats (403)
        admin_stats_resp = await client.get("/api/v1/admin/stats", headers=viewer_headers)
        assert admin_stats_resp.status_code == 403

        # Viewer is forbidden from creating films (403)
        create_resp = await client.post(
            "/api/v1/films",
            json={"title": "Unauthorized Film", "release_year": 2020, "genre": "Action", "director": "Nobody"},
            headers=viewer_headers,
        )
        assert create_resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_stats_and_single_film_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Admin login
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "alice@example.com", "password": "password123"},
        )
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Admin stats
        stats_resp = await client.get("/api/v1/admin/stats", headers=admin_headers)
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert "total_films" in stats
        assert "total_reviews" in stats

        # Fetch films and get single film
        films_resp = await client.get("/api/v1/films", headers=admin_headers)
        assert films_resp.status_code == 200
        film_id = films_resp.json()["data"][0]["id"]

        single_film_resp = await client.get(f"/api/v1/films/{film_id}", headers=admin_headers)
        assert single_film_resp.status_code == 200
        assert single_film_resp.json()["data"]["id"] == film_id

        # Reviews for film
        reviews_resp = await client.get(f"/api/v1/films/{film_id}/reviews", headers=admin_headers)
        assert reviews_resp.status_code == 200


@pytest.mark.asyncio
async def test_film_cache_isolated_operations():
    from app.cache.film_cache import FilmCache
    from app.core.redis import get_redis
    from app.core.redis import redis_client as core_redis_client

    # 1. Verify shared client instance
    dep_client = await get_redis()
    assert dep_client is core_redis_client

    cache = FilmCache(core_redis_client)

    # 2. Verify deterministic key generation
    assert cache.build_key() == "films:list"
    assert cache.build_key(genre="Action") == "films:list:genre=action"
    assert cache.build_key(min_year=2020) == "films:list:min_year=2020"
    assert cache.build_key(max_year=2020) == "films:list:max_year=2020"
    assert cache.build_key(min_year=2000, max_year=2020) == "films:list:min_year=2000:max_year=2020"
    assert cache.build_key(genre=" Action ", min_year=2020) == "films:list:genre=action:min_year=2020"

    # 3. Test get on empty cache
    test_key = cache.build_key(genre="Drama")
    assert await cache.get(test_key) is None

    # 4. Test set and get
    sample_film = {
        "id": "11111111-1111-1111-1111-111111111111",
        "title": "Inception",
        "release_year": 2010,
        "genre": "Sci-Fi",
        "director": "Christopher Nolan",
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    await cache.set(test_key, [sample_film], ttl=30)
    cached_films = await cache.get(test_key)
    assert cached_films is not None
    assert len(cached_films) == 1
    assert cached_films[0].title == "Inception"

    ttl = await core_redis_client.ttl(test_key)
    assert 0 < ttl <= 30

    # 5. Test invalidate
    await cache.invalidate()
    assert await cache.get(test_key) is None
