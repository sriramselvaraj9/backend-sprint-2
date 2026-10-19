"""
tests/integration/test_film_crud.py

Phase Eight: Film CRUD Lifecycle Integration Tests.
Exercises the film API through real HTTP requests and the isolated SQLite database:
A. Admin creates a film.
B. Fetch the film by identifier.
C. Admin updates one field (persisted and verified).
D. Viewer attempts to delete the film (rejected with 403, film remains active).
E. Admin deletes the film (soft-delete verified in database and list endpoints).
"""
#Full CRUD lifecycle integration tests: Admin film creation, retrieval by ID, single-field update (PATCH), Viewer delete rejection (403 Forbidden), and Admin soft deletion verification (is_active = False in DB and omitted from /films).
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.film import Film


@pytest.mark.integration
class TestFilmCRUDLifecycleIntegration:
    """Integration test suite covering the full Film CRUD lifecycle with RBAC."""

    async def test_full_film_crud_lifecycle(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        admin_token: str,
        viewer_token: str,
    ) -> None:
        """
        Execute full Film CRUD lifecycle:
        A. Admin creates a film via POST /api/v1/films.
        B. Fetch the created film via GET /api/v1/films/{film_id}.
        C. Admin updates one field (genre) via PATCH /api/v1/films/{film_id}.
        D. Viewer attempts DELETE /api/v1/films/{film_id} -> 403 Forbidden.
        E. Admin deletes film via DELETE /api/v1/films/{film_id} -> soft-deleted.
        """
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        # -------------------------------------------------------------------
        # A. Admin creates a film
        # -------------------------------------------------------------------
        create_payload = {
            "title": "Oppenheimer",
            "release_year": 2023,
            "genre": "Biography",
            "director": "Christopher Nolan",
        }
        create_response = await client.post(
            "/api/v1/films",
            json=create_payload,
            headers=admin_headers,
        )
        assert create_response.status_code == 200
        created_data = create_response.json()
        assert "id" in created_data
        film_id_str = created_data["id"]
        film_id = uuid.UUID(film_id_str)
        assert created_data["title"] == "Oppenheimer"
        assert created_data["release_year"] == 2023
        assert created_data["genre"] == "Biography"
        assert created_data["director"] == "Christopher Nolan"

        # Verify persistence directly in SQLite database
        stmt = select(Film).where(Film.id == film_id)
        result = await db_session.execute(stmt)
        persisted_film = result.scalar_one_or_none()
        assert persisted_film is not None
        assert persisted_film.title == "Oppenheimer"
        assert persisted_film.is_active is True

        # -------------------------------------------------------------------
        # B. Fetch the film by identifier
        # -------------------------------------------------------------------
        get_response = await client.get(
            f"/api/v1/films/{film_id}",
            headers=viewer_headers,
        )
        assert get_response.status_code == 200
        get_payload = get_response.json()
        film_data = get_payload.get("data", get_payload)
        assert film_data["id"] == film_id_str
        assert film_data["title"] == "Oppenheimer"
        assert film_data["release_year"] == 2023
        assert film_data["genre"] == "Biography"
        assert film_data["director"] == "Christopher Nolan"

        # -------------------------------------------------------------------
        # C. Update one field (genre)
        # -------------------------------------------------------------------
        update_payload = {"genre": "Historical Drama"}
        patch_response = await client.patch(
            f"/api/v1/films/{film_id}",
            json=update_payload,
            headers=admin_headers,
        )
        assert patch_response.status_code == 200
        patch_data = patch_response.json()
        updated_film_field = patch_data.get("film", patch_data).get("genre")
        assert updated_film_field == "Historical Drama"

        # Fetch the film again through GET to confirm persistence via HTTP
        verify_update_resp = await client.get(
            f"/api/v1/films/{film_id}",
            headers=viewer_headers,
        )
        assert verify_update_resp.status_code == 200
        updated_payload = verify_update_resp.json().get("data", verify_update_resp.json())
        assert updated_payload["genre"] == "Historical Drama"

        # Verify persistence in SQLite
        await db_session.refresh(persisted_film)
        assert persisted_film.genre == "Historical Drama"

        # -------------------------------------------------------------------
        # D. Viewer attempts to delete the film (Forbidden)
        # -------------------------------------------------------------------
        viewer_delete_resp = await client.delete(
            f"/api/v1/films/{film_id}",
            headers=viewer_headers,
        )
        assert viewer_delete_resp.status_code == 403
        viewer_err = viewer_delete_resp.json()
        assert "insufficient" in viewer_err.get("detail", "").lower() or viewer_delete_resp.status_code == 403

        # Verify film still exists and is still active in database
        await db_session.refresh(persisted_film)
        assert persisted_film.is_active is True

        # Confirm film is still retrievable via GET
        check_still_exists = await client.get(
            f"/api/v1/films/{film_id}",
            headers=viewer_headers,
        )
        assert check_still_exists.status_code == 200

        # -------------------------------------------------------------------
        # E. Admin deletes the film (Soft Deletion)
        # -------------------------------------------------------------------
        admin_delete_resp = await client.delete(
            f"/api/v1/films/{film_id}",
            headers=admin_headers,
        )
        assert admin_delete_resp.status_code == 200
        admin_del_data = admin_delete_resp.json()
        assert admin_del_data.get("status") == "success"

        # Verify soft deletion in database: row still exists, but is_active is False
        await db_session.refresh(persisted_film)
        assert persisted_film.is_active is False

        # Confirm film no longer appears in GET /api/v1/films catalog
        list_resp = await client.get(
            "/api/v1/films",
            headers=viewer_headers,
        )
        assert list_resp.status_code == 200
        catalog_items = list_resp.json().get("items", [])
        film_ids_in_catalog = [item["id"] for item in catalog_items]
        assert film_id_str not in film_ids_in_catalog

        # Confirm GET /api/v1/films/{film_id} returns 404 (FilmNotFoundError)
        get_deleted_resp = await client.get(
            f"/api/v1/films/{film_id}",
            headers=viewer_headers,
        )
        assert get_deleted_resp.status_code == 404
