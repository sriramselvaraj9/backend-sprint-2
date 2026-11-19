"""
tests/unit/test_review_service.py

Unit tests for ReviewService business logic and review schemas.
Covers:
  - Duplicate review prevention (Rule 1: One review per user per film)
  - Review ownership on update (Rule 2: Only the original reviewer or admin can update)
  - Review ownership on deletion (Only the original reviewer or admin can delete)
  - Film active requirement for review submission
  - Rating and body length validation constraints
"""
#rating constraints, "1 review per user per film" rule, and ownership security (only the author or admin can edit/delete).

import uuid
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.exceptions.domain import (
    FilmNotFoundError,
    ReviewAlreadyExistsError,
    ReviewNotFoundError,
    ReviewUnauthorisedError,
    UserNotFoundError,
)
from app.models.film import Film
from app.models.review import Review
from app.models.user import User
from app.schemas.review import ReviewCreate, ReviewUpdate
from app.services.review_service import ReviewService

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Review Schema & Constraint Validation Tests
# ---------------------------------------------------------------------------


class TestReviewSchemaValidation:
    """Validate review ratings and body text constraints using plain Python objects."""

    def test_valid_review_create(self) -> None:
        """Verify that valid rating (1-10) and body length (10-250) succeed."""
        film_id = uuid.uuid4()
        review = ReviewCreate(
            film_id=film_id,
            rating=8,
            body="An extraordinary film with compelling character arcs and pacing.",
        )
        assert review.film_id == film_id
        assert review.rating == 8
        assert len(review.body) >= 10

    @pytest.mark.parametrize("invalid_rating", [0, -1, 11, 20])
    def test_rating_out_of_bounds_rejected(self, invalid_rating: int) -> None:
        """Verify ratings outside [1, 10] are rejected with validation error."""
        with pytest.raises(ValidationError) as exc_info:
            ReviewCreate(
                film_id=uuid.uuid4(),
                rating=invalid_rating,
                body="Valid body length for this test case.",
            )
        assert any("rating" in str(err["loc"]) for err in exc_info.value.errors())

    @pytest.mark.parametrize("valid_rating", [1, 5, 10])
    def test_rating_boundary_values_accepted(self, valid_rating: int) -> None:
        """Verify ratings at boundaries (1 and 10) are accepted."""
        review = ReviewCreate(
            film_id=uuid.uuid4(),
            rating=valid_rating,
            body="Valid body length for boundary rating test.",
        )
        assert review.rating == valid_rating

    def test_body_too_short_rejected(self) -> None:
        """Verify that a review body shorter than 10 characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ReviewCreate(
                film_id=uuid.uuid4(),
                rating=7,
                body="Too short",  # 9 chars
            )
        assert "body" in str(exc_info.value)

    def test_body_whitespace_trimmed_below_min_rejected(self) -> None:
        """Verify that whitespace-padded body that trims to < 10 chars is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ReviewCreate(
                film_id=uuid.uuid4(),
                rating=7,
                body="   short   ",  # trims to 5 chars
            )
        assert "at least 10 characters" in str(exc_info.value).lower()

    def test_body_too_long_rejected(self) -> None:
        """Verify that a review body exceeding 250 characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ReviewCreate(
                film_id=uuid.uuid4(),
                rating=7,
                body="A" * 251,
            )
        assert "body" in str(exc_info.value)

    def test_review_update_schema_partial(self) -> None:
        """Verify that ReviewUpdate accepts optional rating or body."""
        update_rating_only = ReviewUpdate(rating=9)
        assert update_rating_only.rating == 9
        assert update_rating_only.body is None

        update_body_only = ReviewUpdate(body="Updated detailed thoughts on the movie.")
        assert update_body_only.body == "Updated detailed thoughts on the movie."
        assert update_body_only.rating is None


# ---------------------------------------------------------------------------
# Business Rule 1: Duplicate Review Prevention
# ---------------------------------------------------------------------------


class TestDuplicateReviewPrevention:
    """Verify Business Rule 1: One review per user per film."""

    async def test_duplicate_review_raises_expected_domain_error(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        sample_film: Film,
        viewer_user: User,
        sample_review: Review,
    ) -> None:
        """
        Verify that attempting to create a second review for the same film by the same user
        raises ReviewAlreadyExistsError with the exact film_id and user_id identifiers.
        """
        mock_review_dao.is_film_active.return_value = True
        # Existing review found for this film + user pair
        mock_review_dao.get_by_film_and_user.return_value = sample_review

        payload = ReviewCreate(
            film_id=sample_film.id,
            rating=7,
            body="Attempting to submit a duplicate review for Inception.",
        )

        with pytest.raises(ReviewAlreadyExistsError) as exc_info:
            await review_service.create_review(
                film_id=sample_film.id,
                review_data=payload,
                user_id=viewer_user.id,
            )

        err = exc_info.value
        # Assert exception contract and identifiers
        assert err.film_id == sample_film.id
        assert err.user_id == viewer_user.id
        assert err.error_code == "REVIEW_ALREADY_EXISTS"
        assert err.status_code == 409
        assert err.detail["film_id"] == str(sample_film.id)
        assert err.detail["user_id"] == str(viewer_user.id)

        # Ensure ReviewDAO.create was NOT called
        mock_review_dao.create.assert_not_awaited()

    async def test_first_review_by_user_succeeds(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        sample_film: Film,
        viewer_user: User,
        sample_review: Review,
    ) -> None:
        """Verify that a user who has not yet reviewed the film can submit a review."""
        mock_review_dao.is_film_active.return_value = True
        mock_review_dao.get_by_film_and_user.return_value = None  # No prior review
        mock_review_dao.create.return_value = sample_review

        payload = ReviewCreate(
            film_id=sample_film.id,
            rating=9,
            body="First time reviewing this masterpiece.",
        )

        created = await review_service.create_review(
            film_id=sample_film.id,
            review_data=payload,
            user_id=viewer_user.id,
        )

        assert created == sample_review
        mock_review_dao.create.assert_awaited_once()

    async def test_create_review_on_inactive_or_missing_film_raises_film_not_found(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        sample_film: Film,
        viewer_user: User,
    ) -> None:
        """Verify that reviewing an inactive or nonexistent film raises FilmNotFoundError."""
        mock_review_dao.is_film_active.return_value = False

        payload = ReviewCreate(
            film_id=sample_film.id,
            rating=8,
            body="Trying to review a film that is inactive.",
        )

        with pytest.raises(FilmNotFoundError) as exc_info:
            await review_service.create_review(
                film_id=sample_film.id,
                review_data=payload,
                user_id=viewer_user.id,
            )

        assert exc_info.value.film_id == sample_film.id
        mock_review_dao.get_by_film_and_user.assert_not_awaited()
        mock_review_dao.create.assert_not_awaited()

    async def test_create_review_resolves_fallback_user_id_from_dao(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        mock_user_dao: AsyncMock,
        sample_film: Film,
        viewer_user: User,
        sample_review: Review,
    ) -> None:
        """Verify that when user_id is omitted, ReviewService resolves default user from UserDAO."""
        mock_review_dao.is_film_active.return_value = True
        mock_user_dao.get_default_user.return_value = viewer_user
        mock_review_dao.get_by_film_and_user.return_value = None
        mock_review_dao.create.return_value = sample_review

        payload = ReviewCreate(
            film_id=sample_film.id,
            rating=8,
            body="Review without explicit user id in parameters.",
        )

        created = await review_service.create_review(
            film_id=sample_film.id,
            review_data=payload,
            user_id=None,
        )

        assert created == sample_review
        mock_user_dao.get_default_user.assert_awaited_once()

    async def test_create_review_fails_when_no_user_available(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        mock_user_dao: AsyncMock,
        sample_film: Film,
    ) -> None:
        """Verify that when no user_id is provided and no default user exists, UserNotFoundError is raised."""
        mock_review_dao.is_film_active.return_value = True
        mock_user_dao.get_default_user.return_value = None

        payload = ReviewCreate(
            film_id=sample_film.id,
            rating=8,
            body="Review with no author user anywhere.",
        )

        with pytest.raises(UserNotFoundError):
            await review_service.create_review(
                film_id=sample_film.id,
                review_data=payload,
                user_id=None,
            )


# ---------------------------------------------------------------------------
# Business Rule 2: Review Ownership & Update Authorization
# ---------------------------------------------------------------------------


class TestReviewOwnershipUpdate:
    """Verify Business Rule 2: Only the original reviewer or admin can update a review."""

    async def test_original_author_can_update_own_review(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        sample_review: Review,
        viewer_user: User,
    ) -> None:
        """Verify that the original author can successfully update their own review."""
        mock_review_dao.get_by_id.return_value = sample_review
        sample_review.rating = 10
        sample_review.body = "Updated review: Even better on rewatch!"
        mock_review_dao.update.return_value = sample_review

        update_dto = ReviewUpdate(rating=10, body="Updated review: Even better on rewatch!")

        result = await review_service.update_review(
            review_id=sample_review.id,
            current_user_id=viewer_user.id,
            update_data=update_dto,
            is_admin=False,
        )

        assert result.rating == 10
        assert result.body == "Updated review: Even better on rewatch!"
        mock_review_dao.update.assert_awaited_once()

    async def test_different_user_cannot_update_review_raises_unauthorised(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        sample_review: Review,
        second_viewer_user: User,
    ) -> None:
        """
        Verify that a different user cannot update someone else's review.
        Must raise ReviewUnauthorisedError with review_id and current_user_id.
        """
        mock_review_dao.get_by_id.return_value = sample_review
        # sample_review.user_id != second_viewer_user.id

        update_dto = ReviewUpdate(rating=5, body="Malicious unauthorized edit attempt.")

        with pytest.raises(ReviewUnauthorisedError) as exc_info:
            await review_service.update_review(
                review_id=sample_review.id,
                current_user_id=second_viewer_user.id,
                update_data=update_dto,
                is_admin=False,
            )

        err = exc_info.value
        assert err.review_id == sample_review.id
        assert err.user_id == second_viewer_user.id
        assert err.error_code == "REVIEW_UNAUTHORISED"
        assert err.status_code == 403
        assert err.detail["review_id"] == str(sample_review.id)
        assert err.detail["user_id"] == str(second_viewer_user.id)

        # Ensure ReviewDAO.update was NOT called
        mock_review_dao.update.assert_not_awaited()

    async def test_admin_can_update_any_review(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        sample_review: Review,
        admin_user: User,
    ) -> None:
        """Verify that an admin can update any review regardless of authorship."""
        mock_review_dao.get_by_id.return_value = sample_review
        sample_review.body = "Moderated by administrator."
        mock_review_dao.update.return_value = sample_review

        update_dto = ReviewUpdate(body="Moderated by administrator.")

        result = await review_service.update_review(
            review_id=sample_review.id,
            current_user_id=admin_user.id,
            update_data=update_dto,
            is_admin=True,
        )

        assert result.body == "Moderated by administrator."
        mock_review_dao.update.assert_awaited_once()

    async def test_update_nonexistent_review_raises_not_found(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        viewer_user: User,
    ) -> None:
        """Verify that attempting to update a missing review raises ReviewNotFoundError."""
        missing_id = uuid.uuid4()
        mock_review_dao.get_by_id.return_value = None

        with pytest.raises(ReviewNotFoundError) as exc_info:
            await review_service.update_review(
                review_id=missing_id,
                current_user_id=viewer_user.id,
                rating=8,
            )

        assert exc_info.value.review_id == missing_id
        mock_review_dao.update.assert_not_awaited()


# ---------------------------------------------------------------------------
# Business Rule 3: Review Deletion Permissions
# ---------------------------------------------------------------------------


class TestReviewOwnershipDelete:
    """Verify review deletion permissions: author or admin only."""

    async def test_author_can_delete_own_review(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        sample_review: Review,
        viewer_user: User,
    ) -> None:
        """Verify that the author can delete their own review."""
        mock_review_dao.get_by_id.return_value = sample_review
        mock_review_dao.delete.return_value = sample_review

        deleted = await review_service.delete_review(
            review_id=sample_review.id,
            current_user_id=viewer_user.id,
            is_admin=False,
        )

        assert deleted == sample_review
        mock_review_dao.delete.assert_awaited_once_with(sample_review.id)

    async def test_different_user_cannot_delete_review(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        sample_review: Review,
        second_viewer_user: User,
    ) -> None:
        """Verify that a different user cannot delete someone else's review."""
        mock_review_dao.get_by_id.return_value = sample_review

        with pytest.raises(ReviewUnauthorisedError) as exc_info:
            await review_service.delete_review(
                review_id=sample_review.id,
                current_user_id=second_viewer_user.id,
                is_admin=False,
            )

        err = exc_info.value
        assert err.review_id == sample_review.id
        assert err.user_id == second_viewer_user.id
        mock_review_dao.delete.assert_not_awaited()

    async def test_admin_can_delete_any_review(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        sample_review: Review,
        admin_user: User,
    ) -> None:
        """Verify that an administrator can delete any review."""
        mock_review_dao.get_by_id.return_value = sample_review
        mock_review_dao.delete.return_value = sample_review

        deleted = await review_service.delete_review(
            review_id=sample_review.id,
            current_user_id=admin_user.id,
            is_admin=True,
        )

        assert deleted == sample_review
        mock_review_dao.delete.assert_awaited_once_with(sample_review.id)

    async def test_delete_missing_review_raises_not_found(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        viewer_user: User,
    ) -> None:
        """Verify deleting a nonexistent review raises ReviewNotFoundError."""
        missing_id = uuid.uuid4()
        mock_review_dao.get_by_id.return_value = None

        with pytest.raises(ReviewNotFoundError):
            await review_service.delete_review(
                review_id=missing_id,
                current_user_id=viewer_user.id,
            )

        mock_review_dao.delete.assert_not_awaited()


# ---------------------------------------------------------------------------
# Review Retrieval & Aggregation Tests
# ---------------------------------------------------------------------------


class TestReviewServiceQueries:
    """Verify review pagination queries and average calculations."""

    async def test_get_film_reviews_active_film(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        sample_film: Film,
        sample_review: Review,
    ) -> None:
        """Verify fetching paginated reviews for an active film."""
        mock_review_dao.is_film_active.return_value = True
        mock_review_dao.list_by_film.return_value = [sample_review]
        mock_review_dao.count_by_film.return_value = 1

        reviews, total = await review_service.get_film_reviews(sample_film.id, page=1, page_size=10)

        assert reviews == [sample_review]
        assert total == 1
        mock_review_dao.list_by_film.assert_awaited_once_with(sample_film.id, limit=10, offset=0)

    async def test_get_film_reviews_inactive_film_raises_not_found(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        sample_film: Film,
    ) -> None:
        """Verify that fetching reviews for an inactive film raises FilmNotFoundError."""
        mock_review_dao.is_film_active.return_value = False

        with pytest.raises(FilmNotFoundError) as exc_info:
            await review_service.get_film_reviews(sample_film.id)

        assert exc_info.value.film_id == sample_film.id
        mock_review_dao.list_by_film.assert_not_awaited()

    async def test_get_average_rating_delegates_to_dao(
        self,
        review_service: ReviewService,
        mock_review_dao: AsyncMock,
        sample_film: Film,
    ) -> None:
        """Verify calculating average rating delegates to ReviewDAO."""
        mock_review_dao.average_rating.return_value = 8.75

        avg = await review_service.get_average_rating(sample_film.id)

        assert avg == 8.75
        mock_review_dao.average_rating.assert_awaited_once_with(sample_film.id)
