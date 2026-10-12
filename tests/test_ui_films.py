import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.film import Film


@pytest.mark.asyncio
async def test_get_ui_films_full_page():
    """
    Test 1: GET /ui/films returns HTTP 200, Content-Type text/html,
    and a complete HTML document containing the search input with htmx attributes.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ui/films")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

        html = response.text
        # Verify valid full HTML document structure
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "Film Search" in html

        # Verify htmx CDN is loaded in document head
        assert "htmx.org" in html

        # Verify search input and required htmx attributes
        assert 'name="q"' in html
        assert 'hx-get="/ui/films/search"' in html
        assert 'hx-trigger="input changed delay:300ms"' in html
        assert 'hx-target="#film-results"' in html
        assert 'hx-swap="innerHTML"' in html

        # Verify stable results container exists
        assert 'id="film-results"' in html

        # Verify initial guidance message is present
        assert "Start typing" in html


@pytest.mark.asyncio
async def test_get_ui_films_search_fragment_matching():
    """
    Test 2: GET /ui/films/search?q=interstellar returns an HTML fragment
    containing the matching film details.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ui/films/search", params={"q": "interstellar"})
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

        fragment = response.text
        # Verify it is an HTML fragment, NOT a complete HTML document
        assert "<!DOCTYPE html>" not in fragment
        assert "<html" not in fragment
        assert "<head>" not in fragment
        assert "<body" not in fragment

        # Verify matching film content is rendered
        assert "Interstellar" in fragment
        assert "2014" in fragment
        assert "Sci-Fi" in fragment
        assert "Christopher Nolan" in fragment


@pytest.mark.asyncio
async def test_get_ui_films_search_case_insensitive():
    """
    Test 3: Search is case-insensitive.
    Searching for uppercase or mixed-case queries matches correctly.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Uppercase
        resp_upper = await client.get("/ui/films/search", params={"q": "INCEPTION"})
        assert resp_upper.status_code == 200
        assert "Inception" in resp_upper.text

        # Lowercase
        resp_lower = await client.get("/ui/films/search", params={"q": "inception"})
        assert resp_lower.status_code == 200
        assert "Inception" in resp_lower.text

        # Mixed-case
        resp_mixed = await client.get("/ui/films/search", params={"q": "iNcEpTiOn"})
        assert resp_mixed.status_code == 200
        assert "Inception" in resp_mixed.text


@pytest.mark.asyncio
async def test_get_ui_films_search_no_matches():
    """
    Test 4: Query with no matches returns HTML containing the friendly empty-state message.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ui/films/search", params={"q": "NonExistentMovieXYZ999"})
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

        fragment = response.text
        assert "No films found" in fragment
        assert "NonExistentMovieXYZ999" in fragment


@pytest.mark.asyncio
async def test_get_ui_films_search_empty_query():
    """
    Test 5: A blank or whitespace-only query returns the active film catalogue.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Empty string
        resp_empty = await client.get("/ui/films/search", params={"q": ""})
        assert resp_empty.status_code == 200
        assert "film-card" in resp_empty.text

        # Whitespace-only string
        resp_spaces = await client.get("/ui/films/search", params={"q": "   "})
        assert resp_spaces.status_code == 200
        assert "film-card" in resp_spaces.text


@pytest.mark.asyncio
async def test_get_ui_films_search_rating_display():
    """
    Test 6: Films with reviews render formatted average rating (e.g., '10.0 / 10' or '8.0 / 10'),
    while films without reviews display 'Not rated'.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 'Inception' has a seed review rating of 10
        resp_inception = await client.get("/ui/films/search", params={"q": "Inception"})
        assert resp_inception.status_code == 200
        assert "10.0 / 10" in resp_inception.text

        # 'Blade Runner 2049' has no reviews -> 'Not rated'
        resp_blade_runner = await client.get("/ui/films/search", params={"q": "Blade Runner 2049"})
        assert resp_blade_runner.status_code == 200
        assert "Not rated" in resp_blade_runner.text


@pytest.mark.asyncio
async def test_get_ui_films_search_excludes_inactive_films():
    """
    Test 7: Soft-deleted (is_active == False) films are excluded from UI search results.
    """
    async with SessionLocal() as db:
        # Create an inactive test film
        inactive_film = Film(
            title="Ghost Inactive Film",
            release_year=2020,
            genre="Mystery",
            director="Unknown",
            is_active=False,
        )
        db.add(inactive_film)
        await db.commit()
        await db.refresh(inactive_film)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/ui/films/search", params={"q": "Ghost Inactive Film"})
            assert response.status_code == 200
            # Ensure no film card was rendered for inactive film
            assert "film-card" not in response.text
            assert "No films found" in response.text
    finally:
        # Clean up inactive film
        async with SessionLocal() as db:
            stmt = select(Film).where(Film.title == "Ghost Inactive Film")
            res = await db.execute(stmt)
            f = res.scalar_one_or_none()
            if f:
                await db.delete(f)
                await db.commit()


@pytest.mark.asyncio
async def test_existing_json_api_routes_unaffected():
    """
    Test 8: Existing JSON API routes still function normally and return JSON payloads.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Health check
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"

        # Login to get auth token
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "charlie@example.com", "password": "password123"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        # API films endpoint
        api_films_resp = await client.get(
            "/api/v1/films",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert api_films_resp.status_code == 200
        assert "application/json" in api_films_resp.headers.get("content-type", "")
        data = api_films_resp.json()
        assert "data" in data
        assert isinstance(data["data"], list)


def test_frontend_companion_app_structure_and_config():
    """
    Test 9: Verify Next.js companion app files, package.json, tsconfig.json,
    and configurable iframe URL environment variables.
    """
    from pathlib import Path

    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    assert (frontend_dir / "package.json").exists()
    assert (frontend_dir / "tsconfig.json").exists()
    assert (frontend_dir / "app" / "page.tsx").exists()
    assert (frontend_dir / "app" / "layout.tsx").exists()
    assert (frontend_dir / ".env.example").exists()

    env_example_content = (frontend_dir / ".env.example").read_text(encoding="utf-8")
    assert "NEXT_PUBLIC_FILM_UI_URL" in env_example_content
    assert "/ui/films" in env_example_content

    page_content = (frontend_dir / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "NEXT_PUBLIC_FILM_UI_URL" in page_content
    assert "iframe" in page_content
    assert "title=" in page_content

