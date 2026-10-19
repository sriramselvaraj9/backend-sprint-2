"""
tests/unit/test_film_filters.py

Unit tests for Film filtering, calculation, and schema validation logic.
Tests run purely in memory using plain Python objects with zero external dependencies
(no database, no Redis, no network).
"""
#Pydantic input models, year boundaries, computed fields (years_ago), and in-memory list filtering.

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.film import Film
from app.schemas.film import (
    FilmCreate,
    FilmFilterParams,
    FilmResponse,
    FilmYearRange,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Schema Validation & Business Rule Tests
# ---------------------------------------------------------------------------


class TestFilmSchemaValidation:
    """Validate film input constraints, release year boundaries, and field validation."""

    def test_valid_film_create(self) -> None:
        """Verify that valid film parameters construct a proper FilmCreate model."""
        payload = {
            "title": "Interstellar",
            "release_year": 2014,
            "genre": "Sci-Fi",
            "director": "Christopher Nolan",
        }
        film_create = FilmCreate(**payload)
        assert film_create.title == "Interstellar"
        assert film_create.release_year == 2014
        assert film_create.genre == "Sci-Fi"
        assert film_create.director == "Christopher Nolan"

    def test_release_year_earliest_boundary_1888(self) -> None:
        """Verify that the earliest allowed cinema release year is 1888."""
        valid_film = FilmCreate(
            title="Roundhay Garden Scene",
            release_year=1888,
            genre="Documentary",
            director="Louis Le Prince",
        )
        assert valid_film.release_year == 1888

        invalid_payload = {
            "title": "Too Early",
            "release_year": 1887,
            "genre": "Documentary",
            "director": "Unknown",
        }
        with pytest.raises(ValidationError) as exc_info:
            FilmCreate(**invalid_payload)
        errors = exc_info.value.errors()
        assert any("release_year" in str(err["loc"]) for err in errors)

    def test_release_year_future_boundary(self) -> None:
        """Verify that release_year cannot exceed 5 years into the future."""
        current_year = datetime.now(UTC).year
        max_allowed_year = current_year + 5

        # Exactly at max limit is allowed
        film_ok = FilmCreate(
            title="Future Classic",
            release_year=max_allowed_year,
            genre="Sci-Fi",
            director="Visionary Director",
        )
        assert film_ok.release_year == max_allowed_year

        # Exceeding max limit is rejected
        with pytest.raises(ValidationError) as exc_info:
            FilmCreate(
                title="Far Future Movie",
                release_year=max_allowed_year + 1,
                genre="Sci-Fi",
                director="Time Traveler",
            )
        assert "release_year cannot be more than 5 years in the future" in str(exc_info.value)

    def test_empty_title_rejected(self) -> None:
        """Verify that an empty title string fails min_length validation."""
        with pytest.raises(ValidationError) as exc_info:
            FilmCreate(
                title="",
                release_year=2020,
                genre="Action",
                director="Director Name",
            )
        assert any("title" in str(err["loc"]) for err in exc_info.value.errors())


# ---------------------------------------------------------------------------
# Computed Property & Calculation Tests
# ---------------------------------------------------------------------------


class TestFilmCalculations:
    """Validate calculated attributes such as years_ago and UUID parsing."""

    def test_years_ago_calculation_for_past_film(self) -> None:
        """Verify that years_ago correctly computes the elapsed years since release."""
        current_year = datetime.now(UTC).year
        film_response = FilmResponse(
            id=uuid.uuid4(),
            title="The Godfather",
            release_year=1972,
            genre="Crime",
            director="Francis Ford Coppola",
            review_count=10,
            average_rating=9.2,
        )
        expected_years_ago = current_year - 1972
        assert film_response.years_ago == expected_years_ago

    def test_years_ago_for_current_and_future_release(self) -> None:
        """Verify that years_ago is capped at 0 for current and future releases."""
        current_year = datetime.now(UTC).year
        film_response = FilmResponse(
            id=uuid.uuid4(),
            title="Upcoming Blockbuster",
            release_year=current_year + 1,
            genre="Action",
            director="Future Director",
        )
        assert film_response.years_ago == 0

    def test_parse_id_from_string_and_uuid(self) -> None:
        """Verify that string UUIDs are normalized to uuid.UUID objects."""
        raw_uuid_str = "12345678-1234-5678-1234-567812345678"
        resp = FilmResponse(
            id=raw_uuid_str,  # type: ignore[arg-type]
            title="Parser Test",
            release_year=2020,
            genre="Comedy",
            director="Director",
        )
        assert isinstance(resp.id, uuid.UUID)
        assert str(resp.id) == raw_uuid_str


# ---------------------------------------------------------------------------
# Filter and Range Validation Tests
# ---------------------------------------------------------------------------


class TestFilmFilterRanges:
    """Validate year range logic for film filtering schemas."""

    def test_film_year_range_valid(self) -> None:
        """Verify that start_year strictly less than end_year is valid."""
        year_range = FilmYearRange(start_year=1990, end_year=2000)
        assert year_range.start_year == 1990
        assert year_range.end_year == 2000

    @pytest.mark.parametrize(
        "start_year,end_year",
        [
            (2000, 2000),  # equal
            (2010, 1990),  # inverted
        ],
    )
    def test_film_year_range_invalid(self, start_year: int, end_year: int) -> None:
        """Verify that start_year >= end_year raises a ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            FilmYearRange(start_year=start_year, end_year=end_year)
        assert "start_year must be strictly less than end_year" in str(exc_info.value)

    def test_film_filter_params_from_to_year_valid(self) -> None:
        """Verify that from_year <= to_year is accepted."""
        params = FilmFilterParams(genre="Action", from_year=2000, to_year=2020)
        assert params.genre == "Action"
        assert params.from_year == 2000
        assert params.to_year == 2020

    def test_film_filter_params_inverted_years_rejected(self) -> None:
        """Verify that from_year > to_year raises a ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            FilmFilterParams(from_year=2020, to_year=2000)
        assert "from_year cannot be greater than to_year" in str(exc_info.value)

    def test_film_filter_params_aliases(self) -> None:
        """Verify that min_year and max_year aliases validate correctly."""
        params = FilmFilterParams(min_year=1995, max_year=2005)
        assert params.min_year == 1995
        assert params.max_year == 2005

        with pytest.raises(ValidationError) as exc_info:
            FilmFilterParams(min_year=2015, max_year=2005)
        assert "from_year cannot be greater than to_year" in str(exc_info.value)


# ---------------------------------------------------------------------------
# In-Memory Film Filtering Logic Tests
# ---------------------------------------------------------------------------


class TestInMemoryFilmFiltering:
    """Validate pure Python filtering logic over lists of Film domain objects."""

    @pytest.fixture
    def catalog(self) -> list[Film]:
        """Provide a diverse in-memory catalog of films for filtering tests."""
        return [
            Film(id=uuid.uuid4(), title="Inception", release_year=2010, genre="Sci-Fi", director="Christopher Nolan"),
            Film(
                id=uuid.uuid4(), title="Interstellar", release_year=2014, genre="Sci-Fi", director="Christopher Nolan"
            ),
            Film(id=uuid.uuid4(), title="The Prestige", release_year=2006, genre="Drama", director="Christopher Nolan"),
            Film(id=uuid.uuid4(), title="Pulp Fiction", release_year=1994, genre="Crime", director="Quentin Tarantino"),
            Film(id=uuid.uuid4(), title="Kill Bill", release_year=2003, genre="Action", director="Quentin Tarantino"),
        ]

    def test_filter_by_genre(self, catalog: list[Film]) -> None:
        """Verify exact genre filtering in memory."""
        sci_fi = [f for f in catalog if f.genre.lower() == "sci-fi"]
        assert len(sci_fi) == 2
        assert {f.title for f in sci_fi} == {"Inception", "Interstellar"}

    def test_filter_by_year_range(self, catalog: list[Film]) -> None:
        """Verify inclusive year range filtering in memory."""
        filtered = [f for f in catalog if 2000 <= f.release_year <= 2010]
        assert len(filtered) == 3
        assert {f.title for f in filtered} == {"Inception", "The Prestige", "Kill Bill"}

    def test_filter_by_director_substring_case_insensitive(self, catalog: list[Film]) -> None:
        """Verify case-insensitive partial director matching."""
        filtered = [f for f in catalog if "tarantino" in f.director.lower()]
        assert len(filtered) == 2
        assert {f.title for f in filtered} == {"Pulp Fiction", "Kill Bill"}
