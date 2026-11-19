"""
tests/unit/test_review_events.py

Unit tests for Day 7 Exercise: Publishing Review Events using SQS Queue.
Tests cover:
  1. Creating a review schedules a ReviewCreated event.
  2. Updating a review schedules a ReviewUpdated event.
  3. The event payload contains only event_type, review_id, and timestamp.
  4. The full review record is not included in the message.
  5. Publishing is scheduled using BackgroundTasks rather than awaited inside the handler.
  6. Queue unavailability during startup does not prevent application startup.
  7. A publishing failure is logged and does not crash the request flow.
"""

import json
import logging
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi import BackgroundTasks
from pydantic import ValidationError

from app.handlers.review_handler import ReviewHandler
from app.models.review import Review
from app.schemas.event import ReviewEvent
from app.schemas.review import ReviewCreate, ReviewUpdate
from app.services.event_publisher import EventPublisher, SQSEventPublisher
from app.services.review_service import ReviewService

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Tests 3 & 4: Typed Event Payload Structure
# ---------------------------------------------------------------------------
class TestReviewEventPayload:
    """Verifies that the event payload strictly adheres to the minimal schema."""

    def test_payload_contains_only_required_fields(self) -> None:
        """Requirement 3: The event payload contains only event_type, review_id, and timestamp."""
        event = ReviewEvent(
            event_type="ReviewCreated",
            review_id="review-101",
            timestamp="2026-11-16T10:00:00Z",
        )
        data = event.model_dump()

        assert set(data.keys()) == {"event_type", "review_id", "timestamp"}
        assert data["event_type"] == "ReviewCreated"
        assert data["review_id"] == "review-101"
        assert data["timestamp"] == "2026-11-16T10:00:00Z"

    def test_payload_defaults_timestamp_if_omitted(self) -> None:
        """Verifies timestamp is automatically populated as an ISO string when omitted."""
        event = ReviewEvent(
            event_type="ReviewUpdated",
            review_id="review-202",
        )
        assert event.timestamp is not None
        assert "T" in event.timestamp

    def test_full_review_record_and_extra_fields_are_forbidden(self) -> None:
        """Requirement 4: Full review record (rating, body, user details) is forbidden."""
        with pytest.raises(ValidationError):
            ReviewEvent(
                event_type="ReviewCreated",
                review_id="review-101",
                rating=10,  # forbidden
                body="This should not be in the event",  # forbidden
            )

    def test_serialization_to_json(self) -> None:
        """Verifies serialized JSON matches the required structure."""
        event = ReviewEvent(
            event_type="ReviewCreated",
            review_id="review-101",
            timestamp="2026-11-16T10:00:00Z",
        )
        json_str = event.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed == {
            "event_type": "ReviewCreated",
            "review_id": "review-101",
            "timestamp": "2026-11-16T10:00:00Z",
        }


# ---------------------------------------------------------------------------
# Tests 1, 2, & 5: ReviewHandler Event Scheduling with BackgroundTasks
# ---------------------------------------------------------------------------
class TestReviewHandlerEventScheduling:
    """Verifies that ReviewHandler registers event publishing with BackgroundTasks."""

    async def test_create_review_schedules_review_created_event(self) -> None:
        """
        Requirements 1 & 5:
        Creating a review schedules a ReviewCreated event using BackgroundTasks,
        rather than awaiting inside the handler.
        """
        mock_service = AsyncMock(spec=ReviewService)
        mock_publisher = MagicMock(spec=EventPublisher)
        review_id = uuid.uuid4()
        film_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_review = Review(
            id=review_id,
            film_id=film_id,
            user_id=user_id,
            rating=9,
            body="A spectacular cinematic experience.",
        )
        mock_service.create_review.return_value = mock_review

        handler = ReviewHandler(service=mock_service, event_publisher=mock_publisher)
        background_tasks = BackgroundTasks()

        create_data = ReviewCreate(
            film_id=film_id,
            rating=9,
            body="A spectacular cinematic experience.",
        )

        response = await handler.create_film_review(
            film_id=film_id,
            review_data=create_data,
            user_id=user_id,
            background_tasks=background_tasks,
        )

        # 1. Verify normal response returned immediately
        assert response["id"] == review_id
        assert response["rating"] == 9

        # 2. Verify publishing was NOT called synchronously inside handler
        mock_publisher.publish_review_event.assert_not_called()

        # 3. Verify task is registered in BackgroundTasks
        assert len(background_tasks.tasks) == 1
        task = background_tasks.tasks[0]
        assert task.func == mock_publisher.publish_review_event
        assert task.kwargs == {"event_type": "ReviewCreated", "review_id": str(review_id)}

    async def test_update_review_schedules_review_updated_event(self) -> None:
        """
        Requirements 2 & 5:
        Updating a review schedules a ReviewUpdated event using BackgroundTasks,
        rather than awaiting inside the handler.
        """
        mock_service = AsyncMock(spec=ReviewService)
        mock_publisher = MagicMock(spec=EventPublisher)
        review_id = uuid.uuid4()
        mock_updated = Review(
            id=review_id,
            film_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            rating=8,
            body="Updated review body with new thoughts.",
        )
        mock_service.update_review.return_value = mock_updated

        handler = ReviewHandler(service=mock_service, event_publisher=mock_publisher)
        background_tasks = BackgroundTasks()

        update_data = ReviewUpdate(rating=8, body="Updated review body with new thoughts.")

        response = await handler.update_review(
            review_id=review_id,
            update_data=update_data,
            background_tasks=background_tasks,
        )

        # 1. Verify normal response returned immediately
        assert response["status"] == "success"
        assert response["review_id"] == str(review_id)

        # 2. Verify publishing was NOT called synchronously inside handler
        mock_publisher.publish_review_event.assert_not_called()

        # 3. Verify task is registered in BackgroundTasks
        assert len(background_tasks.tasks) == 1
        task = background_tasks.tasks[0]
        assert task.func == mock_publisher.publish_review_event
        assert task.kwargs == {"event_type": "ReviewUpdated", "review_id": str(review_id)}


# ---------------------------------------------------------------------------
# Tests 6 & 7: Fault Tolerance (Queue Unavailability & Publishing Failures)
# ---------------------------------------------------------------------------
class TestEventPublisherFaultTolerance:
    """Verifies that queue connection and publishing failures are safely handled."""

    def test_startup_queue_unavailability_does_not_crash(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        Requirement 6: Queue unavailability during startup does not prevent application startup.
        A clear warning must be logged.
        """
        publisher = SQSEventPublisher()

        # Mock SQS client to raise EndpointConnectionError
        mock_sqs = MagicMock()
        mock_sqs.get_queue_url.side_effect = EndpointConnectionError(endpoint_url="http://localhost:4566")

        with patch.object(publisher, "_sqs_client", mock_sqs):
            with caplog.at_level(logging.WARNING):
                is_healthy = publisher.check_queue_health()

            # Must return False and NOT raise an exception
            assert is_healthy is False
            # Must log a clear warning
            assert any(
                "unreachable" in rec.message.lower() or "check failed" in rec.message.lower()
                for rec in caplog.records
            )

    def test_publishing_failure_is_logged_and_does_not_crash(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        Requirement 7: A publishing failure is logged and does not crash the request flow.
        """
        publisher = SQSEventPublisher()

        mock_sqs = MagicMock()
        mock_sqs.get_queue_url.return_value = {"QueueUrl": "http://localhost:4566/000000000000/review-events-queue"}
        mock_sqs.send_message.side_effect = ClientError(
            {"Error": {"Code": "AWS.SimpleQueueService.NonExistentQueue", "Message": "Queue does not exist"}},
            "SendMessage",
        )

        with patch.object(publisher, "_sqs_client", mock_sqs):
            with caplog.at_level(logging.ERROR):
                # Must NOT raise an exception
                publisher.publish_review_event(event_type="ReviewCreated", review_id="review-101")

            # Must log error with details
            assert any("Failed to publish 'ReviewCreated' event for review review-101" in rec.message for rec in caplog.records)
