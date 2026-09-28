from datetime import datetime
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas.film import FilmCreate, FilmResponse, FilmYearRange
from app.schemas.review import ReviewCreate, ReviewResponse
from app.schemas.user import UserCreate, UserResponse


client = TestClient(app)


def test_1_valid_film():
    """Case 1: Valid film payload."""
    payload = {
        "title": "Inception",
        "release_year": 2010,
        "genre": "Sci-Fi",
        "director": "Christopher Nolan",
    }
    # Direct Pydantic validation
    film = FilmCreate(**payload)
    assert film.title == "Inception"
    assert film.release_year == 2010

    # API Endpoint validation
    response = client.post("/api/v1/films", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["title"] == "Inception"
    assert data["release_year"] == 2010
    assert data["genre"] == "Sci-Fi"
    assert data["director"] == "Christopher Nolan"
    assert "years_ago" in data
    assert data["years_ago"] == datetime.now().year - 2010
    print("[PASS] Test 1: Valid film accepted and processed correctly.")


def test_2_invalid_film_type_strict_mode():
    """Case 2: Invalid film type with release_year as string '2010' must be rejected."""
    payload = {
        "title": "Inception",
        "release_year": "2010",  # String instead of int
        "genre": "Sci-Fi",
        "director": "Christopher Nolan",
    }
    # Direct Pydantic strict mode validation
    rejected = False
    try:
        FilmCreate.model_validate(payload)
    except ValidationError as exc:
        rejected = True
        errors = exc.errors()
        assert any("release_year" in str(err["loc"]) for err in errors)
    assert rejected, "Strict mode must reject string for int"

    # API Endpoint validation
    response = client.post("/api/v1/films", json=payload)
    assert response.status_code == 422, "Strict mode must reject string for int"
    print("[PASS] Test 2: Invalid film release_year type '2010' rejected by strict mode.")


def test_3_valid_review():
    """Case 3: Valid review payload with >=50 chars body and 1<=rating<=10."""
    payload = {
        "film_id": 1,
        "rating": 8,
        "body": "This is a detailed review containing more than fifty characters.",
    }
    # Direct Pydantic validation
    review = ReviewCreate(**payload)
    assert review.rating == 8
    assert review.film_id == 1

    # API Endpoint validation
    response = client.post("/api/v1/reviews", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["film_id"] == 1
    assert data["rating"] == 8
    assert data["body"] == payload["body"]
    assert "reviewer_display_name" in data
    assert "submitted_at" in data
    print("[PASS] Test 3: Valid review accepted and processed correctly.")


def test_4_invalid_rating():
    """Case 4: Invalid rating (11) must be rejected."""
    payload = {
        "film_id": 1,
        "rating": 11,
        "body": "This is a detailed review containing more than fifty characters.",
    }
    # Direct Pydantic validation
    rejected = False
    try:
        ReviewCreate(**payload)
    except ValidationError:
        rejected = True
    assert rejected, "Rating 11 must be rejected by Field(ge=1, le=10)"

    # API Endpoint validation
    response = client.post("/api/v1/reviews", json=payload)
    assert response.status_code == 422
    print("[PASS] Test 4: Rating out of bounds (11) rejected.")


def test_5_invalid_review_body():
    """Case 5: Body shorter than 50 characters must be rejected."""
    payload = {
        "film_id": 1,
        "rating": 8,
        "body": "Too short.",
    }
    # Direct Pydantic validation
    rejected = False
    try:
        ReviewCreate(**payload)
    except ValidationError:
        rejected = True
    assert rejected, "Review body < 50 characters must be rejected"

    # API Endpoint validation
    response = client.post("/api/v1/reviews", json=payload)
    assert response.status_code == 422
    print("[PASS] Test 5: Review body with <50 characters rejected.")


def test_6_user_response_no_password():
    """Case 6: UserResponse exposes username, email, role, but NEVER password."""
    # Direct Pydantic validation
    user_resp = UserResponse(username="john_doe", email="john@example.com", role="member")
    dumped = user_resp.model_dump()
    assert "username" in dumped
    assert "email" in dumped
    assert "role" in dumped
    assert "password" not in dumped

    # API Endpoint registration
    reg_payload = {
        "username": "sriram_m",
        "email": "sriram@example.com",
        "password": "supersecretpassword123",
    }
    response = client.post("/api/v1/auth/register", json=reg_payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["username"] == "sriram_m"
    assert data["email"] == "sriram@example.com"
    assert data["role"] == "user"
    assert "password" not in data, "Password must NEVER be exposed in UserResponse!"

    # API Endpoint /users/me
    response_me = client.get("/api/v1/users/me")
    assert response_me.status_code == 200
    me_data = response_me.json()
    assert "password" not in me_data
    print("[PASS] Test 6: UserResponse masks password successfully across schemas and endpoints.")


def test_7_computed_field_years_ago():
    """Case 7: years_ago is computed automatically from release_year."""
    film_resp = FilmResponse(
        id=42,
        title="Interstellar",
        release_year=2014,
        genre="Sci-Fi",
        director="Christopher Nolan",
    )
    expected_years = datetime.now().year - 2014
    assert film_resp.years_ago == expected_years
    dumped = film_resp.model_dump()
    assert "years_ago" in dumped
    assert dumped["years_ago"] == expected_years
    print(f"[PASS] Test 7: Computed field 'years_ago' calculated: {expected_years}.")


def test_8_model_validator_year_range():
    """Case 8: @model_validator(mode='after') rejects start_year >= end_year."""
    # Valid range
    valid_range = FilmYearRange(start_year=2000, end_year=2010)
    assert valid_range.start_year == 2000
    assert valid_range.end_year == 2010

    # Invalid range: start_year > end_year
    rejected_greater = False
    try:
        FilmYearRange(start_year=2020, end_year=2010)
    except ValidationError as exc:
        rejected_greater = True
        assert "start_year must be strictly less than end_year" in str(exc)
    assert rejected_greater

    # Invalid range: start_year == end_year
    rejected_equal = False
    try:
        FilmYearRange(start_year=2020, end_year=2020)
    except ValidationError as exc2:
        rejected_equal = True
        assert "start_year must be strictly less than end_year" in str(exc2)
    assert rejected_equal

    # Via Endpoint
    bad_resp = client.post("/api/v1/films/filter/year-range", json={"start_year": 2025, "end_year": 2020})
    assert bad_resp.status_code == 422

    good_resp = client.post("/api/v1/films/filter/year-range", json={"start_year": 2010, "end_year": 2020})
    assert good_resp.status_code == 200
    print("[PASS] Test 8: Model-level validator correctly enforces start_year < end_year.")


def test_9_str_strip_whitespace():
    """Case 9: str_strip_whitespace=True strips whitespace."""
    film = FilmCreate(
        title="   The Matrix   ",
        release_year=1999,
        genre="   Action   ",
        director="   The Wachowskis   ",
    )
    assert film.title == "The Matrix"
    assert film.genre == "Action"
    assert film.director == "The Wachowskis"
    print("[PASS] Test 9: Whitespace stripping verified.")


def test_10_model_dump_and_model_dump_json():
    """Case 10: model_dump() and model_dump_json() serialization."""
    film = FilmCreate(
        title="Dune",
        release_year=2021,
        genre="Sci-Fi",
        director="Denis Villeneuve",
    )
    d = film.model_dump()
    assert isinstance(d, dict)
    assert d["title"] == "Dune"

    j = film.model_dump_json()
    assert isinstance(j, str)
    assert '"title":"Dune"' in j or '"title": "Dune"' in j
    print("[PASS] Test 10: model_dump() and model_dump_json() verified.")


if __name__ == "__main__":
    test_1_valid_film()
    test_2_invalid_film_type_strict_mode()
    test_3_valid_review()
    test_4_invalid_rating()
    test_5_invalid_review_body()
    test_6_user_response_no_password()
    test_7_computed_field_years_ago()
    test_8_model_validator_year_range()
    test_9_str_strip_whitespace()
    test_10_model_dump_and_model_dump_json()
    print("\n>>> ALL 10 TESTS PASSED SUCCESSFULLY! <<<")
