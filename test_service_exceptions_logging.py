"""
Comprehensive verification test suite for Service Layer, Centralized Exceptions,
and Structured JSON Logging with JWT Authentication.
"""

import asyncio
import io
import json
import logging
import uuid

import httpx
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.database import SessionLocal, engine, init_db
from app.logging_config import StructuredJsonFormatter
from app.main import app
from app.models.film import Film
from app.models.user import User


async def run_comprehensive_tests():
    print("=" * 70)
    print("RUNNING SERVICE LAYER, EXCEPTIONS & STRUCTURED LOGGING TEST SUITE")
    print("=" * 70)

    # 0. Initialize Database
    await init_db()

    # Capture logs to verify JSON structure and request trace IDs
    log_capture_stream = io.StringIO()
    root_logger = logging.getLogger()
    capture_handler = logging.StreamHandler(log_capture_stream)
    capture_handler.setFormatter(StructuredJsonFormatter())
    root_logger.addHandler(capture_handler)

    async with SessionLocal() as db:
        # Seed test users
        u1_stmt = select(User).where(User.username == "alice_critic")
        res1 = await db.execute(u1_stmt)
        user_alice = res1.scalar_one_or_none()
        if not user_alice:
            user_alice = User(
                username="alice_critic",
                email="alice@critics.com",
                password_hash=hash_password("password123"),
                role="reviewer",
            )
            db.add(user_alice)
            await db.commit()
            await db.refresh(user_alice)

        u2_stmt = select(User).where(User.username == "bob_viewer")
        res2 = await db.execute(u2_stmt)
        user_bob = res2.scalar_one_or_none()
        if not user_bob:
            user_bob = User(
                username="bob_viewer",
                email="bob@viewers.com",
                password_hash=hash_password("password123"),
                role="user",
            )
            db.add(user_bob)
            await db.commit()
            await db.refresh(user_bob)

        # Seed test films
        f1_stmt = select(Film).where(Film.title == "Dune: Part Two")
        res_f1 = await db.execute(f1_stmt)
        film_dune = res_f1.scalar_one_or_none()
        if not film_dune:
            film_dune = Film(
                title="Dune: Part Two",
                release_year=2024,
                genre="Sci-Fi",
                director="Denis Villeneuve",
            )
            db.add(film_dune)
            await db.commit()
            await db.refresh(film_dune)

        f2_stmt = select(Film).where(Film.title == "Oppenheimer")
        res_f2 = await db.execute(f2_stmt)
        film_oppenheimer = res_f2.scalar_one_or_none()
        if not film_oppenheimer:
            film_oppenheimer = Film(
                title="Oppenheimer",
                release_year=2023,
                genre="Biography",
                director="Christopher Nolan",
            )
            db.add(film_oppenheimer)
            await db.commit()
            await db.refresh(film_oppenheimer)

        # Film without reviews for soft-delete test
        f_solo_title = f"Solo Indie Film {uuid.uuid4().hex[:6]}"
        film_solo = Film(
            title=f_solo_title,
            release_year=2022,
            genre="Drama",
            director="Independent Director",
        )
        db.add(film_solo)
        await db.commit()
        await db.refresh(film_solo)

        alice_id = user_alice.id
        bob_id = user_bob.id
        dune_id = film_dune.id
        solo_id = film_solo.id

        alice_token = create_access_token(
            data={"sub": str(alice_id), "role": user_alice.role, "username": user_alice.username}
        )
        bob_token = create_access_token(data={"sub": str(bob_id), "role": user_bob.role, "username": user_bob.username})

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # ---------------------------------------------------------------------
        # TEST 1: Request-Scoped Logging and Trace ID Propagation
        # ---------------------------------------------------------------------
        print("\n[TEST 1] Verifying Request Trace ID propagation & structured JSON log...")
        custom_trace_id = f"trace-{uuid.uuid4().hex[:8]}"
        res = await client.get(
            "/api/v1/films",
            headers={"X-Request-ID": custom_trace_id, "Authorization": f"Bearer {alice_token}"},
        )
        assert res.status_code == 200
        assert res.headers.get("X-Request-ID") == custom_trace_id
        assert res.json()["trace_id"] == custom_trace_id
        print(f"[PASS] X-Request-ID header reflected in response: {custom_trace_id}")

        # Check captured logs for JSON structure
        log_lines = [line for line in log_capture_stream.getvalue().split("\n") if line.strip()]
        assert len(log_lines) > 0
        parsed_logs = [json.loads(line) for line in log_lines]
        matching_trace_logs = [log for log in parsed_logs if log.get("request_id") == custom_trace_id]
        assert len(matching_trace_logs) > 0, "No log found with the custom request_id"
        sample_log = matching_trace_logs[0]
        assert "level" in sample_log
        assert "timestamp" in sample_log
        assert "logger" in sample_log
        assert "message" in sample_log
        assert sample_log["request_id"] == custom_trace_id
        print(f"[PASS] Structured JSON log validated: {sample_log}")

        # ---------------------------------------------------------------------
        # TEST 2: Rule 1 — One review per user per film
        # ---------------------------------------------------------------------
        print("\n[TEST 2] Testing Business Rule 1: One review per user per film...")
        review_body = "An incredible cinematic achievement with breathtaking sound design and cinematography."

        # First review by Alice for Dune
        res_create1 = await client.post(
            f"/api/v1/films/{dune_id}/reviews",
            json={
                "film_id": str(dune_id),
                "rating": 9,
                "body": review_body,
                "user_id": str(alice_id),
            },
            headers={"X-Request-ID": "req-alice-review-1", "Authorization": f"Bearer {alice_token}"},
        )
        if res_create1.status_code == 200:
            alice_review_id = res_create1.json()["id"]
            print(f"[PASS] Alice created first review for Dune: ID {alice_review_id}")
        elif res_create1.status_code == 409:
            print("[INFO] Alice review already existed from previous run")
        else:
            raise AssertionError(f"Unexpected status code {res_create1.status_code}: {res_create1.text}")

        # Second review attempt by Alice for the SAME film -> MUST FAIL with 409 Conflict
        res_create2 = await client.post(
            f"/api/v1/films/{dune_id}/reviews",
            json={
                "film_id": str(dune_id),
                "rating": 10,
                "body": "Attempting a duplicate review for the same film by the same reviewer Alice.",
                "user_id": str(alice_id),
            },
            headers={"X-Request-ID": "req-alice-duplicate", "Authorization": f"Bearer {alice_token}"},
        )
        assert res_create2.status_code == 409, f"Expected 409 Conflict, got {res_create2.status_code}"
        err_data = res_create2.json()
        print(f"[PASS] Duplicate review rejected with 409 Conflict: {err_data}")
        assert err_data["type"] == "ReviewAlreadyExistsError"
        assert "already submitted a review" in err_data["message"]
        assert err_data["detail"]["film_id"] == str(dune_id)
        assert err_data["detail"]["user_id"] == str(alice_id)

        # Bob creates review for the SAME film -> MUST SUCCEED (different user)
        res_bob = await client.post(
            f"/api/v1/films/{dune_id}/reviews",
            json={
                "film_id": str(dune_id),
                "rating": 8,
                "body": "A great sequel that expands the world and deepens the political intrigue nicely.",
                "user_id": str(bob_id),
            },
            headers={"X-Request-ID": "req-bob-review", "Authorization": f"Bearer {bob_token}"},
        )
        if res_bob.status_code == 200:
            bob_review_id = res_bob.json()["id"]
            print(f"[PASS] Bob created review for Dune successfully: ID {bob_review_id}")
        else:
            assert res_bob.status_code in [200, 409]

        # ---------------------------------------------------------------------
        # TEST 3: Rule 2 — Only the original reviewer can update
        # ---------------------------------------------------------------------
        print("\n[TEST 3] Testing Business Rule 2: Only original reviewer can update review...")
        # Get all reviews for Dune to find Alice's review ID
        res_reviews = await client.get(
            f"/api/v1/films/{dune_id}/reviews",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        reviews_list = res_reviews.json()["reviews"]
        alice_reviews = [r for r in reviews_list if r["reviewer_display_name"] == "alice_critic"]
        assert len(alice_reviews) > 0
        target_alice_review_id = alice_reviews[0]["id"]

        # Bob attempts to update Alice's review -> MUST FAIL with 403 Forbidden
        res_unauth_update = await client.patch(
            f"/api/v1/reviews/{target_alice_review_id}",
            json={
                "rating": 1,
                "body": "Malicious modification attempt by Bob on Alice's film review should fail.",
                "user_id": str(bob_id),
            },
            headers={"X-Request-ID": "req-bob-unauthorized-update", "Authorization": f"Bearer {bob_token}"},
        )
        assert res_unauth_update.status_code == 403, f"Expected 403 Forbidden, got {res_unauth_update.status_code}"
        unauth_err = res_unauth_update.json()
        print(f"[PASS] Unauthorized update rejected with 403 Forbidden: {unauth_err}")
        assert unauth_err["type"] in ["ReviewUnauthorisedError", "ReviewUnauthorizedError"]
        assert "original reviewer" in unauth_err["message"]
        assert unauth_err["detail"]["review_id"] == str(target_alice_review_id)
        assert unauth_err["detail"]["user_id"] == str(bob_id)

        # Alice updates her OWN review -> MUST SUCCEED with 200 OK
        new_alice_body = "Updated Review: An absolute masterpiece that sets a new high standard for science fiction."
        res_auth_update = await client.patch(
            f"/api/v1/reviews/{target_alice_review_id}",
            json={
                "rating": 10,
                "body": new_alice_body,
                "user_id": str(alice_id),
            },
            headers={"X-Request-ID": "req-alice-legit-update", "Authorization": f"Bearer {alice_token}"},
        )
        assert res_auth_update.status_code == 200, (
            f"Expected 200 OK, got {res_auth_update.status_code}: {res_auth_update.text}"
        )
        updated_data = res_auth_update.json()
        print(f"[PASS] Alice successfully updated her own review: {updated_data['message']}")
        assert updated_data["review"]["rating"] == 10
        assert updated_data["review"]["body"] == new_alice_body

        # ---------------------------------------------------------------------
        # TEST 4: Film Soft-Delete Rule
        # ---------------------------------------------------------------------
        print("\n[TEST 4] Testing Business Rule 3: Film soft-delete prohibited when active reviews exist...")

        # Attempt to delete Dune (which has active reviews) -> MUST FAIL with 409 Conflict
        res_del_dune = await client.delete(
            f"/api/v1/films/{dune_id}",
            headers={"X-Request-ID": "req-delete-dune-with-reviews", "Authorization": f"Bearer {alice_token}"},
        )
        assert res_del_dune.status_code == 409, f"Expected 409 Conflict, got {res_del_dune.status_code}"
        del_err = res_del_dune.json()
        print(f"[PASS] Film deletion rejected with 409 Conflict: {del_err}")
        assert del_err["type"] == "FilmHasActiveReviewsError"
        assert "active reviews" in del_err["message"]
        assert del_err["detail"]["film_id"] == str(dune_id)
        assert del_err["detail"]["active_review_count"] >= 1

        # Delete film with NO active reviews (film_solo) -> MUST SUCCEED with 200 OK
        res_del_solo = await client.delete(
            f"/api/v1/films/{solo_id}",
            headers={"X-Request-ID": "req-delete-solo-no-reviews", "Authorization": f"Bearer {alice_token}"},
        )
        assert res_del_solo.status_code == 200, f"Expected 200 OK, got {res_del_solo.status_code}"
        del_solo_data = res_del_solo.json()
        print(f"[PASS] Film with no active reviews soft-deleted successfully: {del_solo_data}")
        assert del_solo_data["status"] == "success"

        # Verifying soft-deleted film is no longer retrievable
        res_get_deleted = await client.get(
            f"/api/v1/films/{solo_id}",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert res_get_deleted.status_code == 404
        assert res_get_deleted.json()["type"] == "FilmNotFoundError"
        print(f"[PASS] Soft-deleted film returns 404 FilmNotFoundError: {res_get_deleted.json()}")

    await engine.dispose()
    print("\n" + "=" * 70)
    print("ALL SERVICE LAYER, EXCEPTION & STRUCTURED LOGGING TESTS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_comprehensive_tests())
