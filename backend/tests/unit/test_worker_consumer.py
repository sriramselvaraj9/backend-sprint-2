"""
tests/unit/test_worker_consumer.py

Unit tests for Day 8: Standalone Event Consumer Worker with DLQ.
Tests cover:
  1. Valid event deserialization.
  2. Correct handler dispatch using registry.
  3. Unknown event type handling (safe discard, warning logged, no crash).
  4. Malformed message handling (invalid JSON, schema validation failure).
  5. Successful processing and message deletion using ReceiptHandle (never MessageId).
  6. Handler failure without message deletion (allowing redelivery).
  7. Duplicate event delivery and database idempotency.
  8. Concurrent duplicate delivery database constraint handling.
  9. Worker continues processing after an individual message failure in a batch.
  10. Simulated handler failure for DLQ redrive testing.
"""

import json
import logging
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.daos.processed_event_dao import ProcessedEventDAO
from app.handlers.event_handlers import (
    EventHandlerRegistry,
    SimulatedHandlerError,
    handle_review_created,
    handle_review_updated,
)
from app.models.film import Film
from app.models.processed_event import ProcessedEvent
from app.models.review import Review
from app.schemas.event import ReviewEvent
from app.services.sqs_consumer import SQSConsumer

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_sqs_client() -> MagicMock:
    """Mock boto3 SQS client."""
    client = MagicMock()
    client.get_queue_url.return_value = {"QueueUrl": "http://localhost:4566/000000000000/review-events-queue"}
    client.delete_message.return_value = {}
    return client


@pytest.fixture
def sample_sqs_message() -> dict[str, Any]:
    """Sample raw SQS message representing a ReviewCreated event."""
    body = {
        "event_type": "ReviewCreated",
        "review_id": "11111111-1111-1111-1111-111111111111",
        "event_id": "evt-test-001",
        "timestamp": "2026-11-17T12:00:00Z",
    }
    return {
        "MessageId": "msg-sqs-001",
        "ReceiptHandle": "receipt-handle-abc-123",
        "Body": json.dumps(body),
    }


# ---------------------------------------------------------------------------
# 1. Valid Event Deserialization
# ---------------------------------------------------------------------------
class TestEventDeserialization:
    """Verifies that the consumer deserializes raw JSON into typed ReviewEvent models."""

    def test_valid_review_created_payload(self) -> None:
        raw_body = json.dumps({
            "event_type": "ReviewCreated",
            "review_id": "11111111-1111-1111-1111-111111111111",
            "event_id": "evt-123",
            "timestamp": "2026-11-17T10:00:00Z",
        })
        event = ReviewEvent.model_validate_json(raw_body)
        assert event.event_type == "ReviewCreated"
        assert event.review_id == "11111111-1111-1111-1111-111111111111"
        assert event.event_id == "evt-123"
        assert event.timestamp == "2026-11-17T10:00:00Z"

    def test_valid_review_updated_payload(self) -> None:
        raw_body = json.dumps({
            "event_type": "ReviewUpdated",
            "review_id": "22222222-2222-2222-2222-222222222222",
        })
        event = ReviewEvent.model_validate_json(raw_body)
        assert event.event_type == "ReviewUpdated"
        assert event.review_id == "22222222-2222-2222-2222-222222222222"
        assert event.event_id is None  # Defaults to None if omitted


# ---------------------------------------------------------------------------
# 2. Handler Registry and Correct Dispatch
# ---------------------------------------------------------------------------
class TestHandlerRegistryDispatch:
    """Verifies typed routing via EventHandlerRegistry."""

    def test_registry_registration_and_retrieval(self) -> None:
        registry = EventHandlerRegistry()
        mock_handler = AsyncMock()
        registry.register("ReviewCreated", mock_handler)

        assert registry.is_supported("ReviewCreated") is True
        assert registry.is_supported("UnknownType") is False
        assert registry.get_handler("ReviewCreated") == mock_handler
        assert registry.get_handler("UnknownType") is None

    async def test_consumer_dispatches_to_registered_handler(
        self,
        mock_sqs_client: MagicMock,
        sample_sqs_message: dict[str, Any],
    ) -> None:
        mock_handler = AsyncMock(return_value={"status": "processed"})
        registry = EventHandlerRegistry()
        registry.register("ReviewCreated", mock_handler)

        mock_session = AsyncMock(spec=AsyncSession)
        session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__.return_value = mock_session

        consumer = SQSConsumer(
            sqs_client=mock_sqs_client,
            registry=registry,
            session_factory=session_factory,
        )

        acknowledged = await consumer.process_single_message(sample_sqs_message, "http://queue-url")

        assert acknowledged is True
        mock_handler.assert_called_once()
        call_kwargs = mock_handler.call_args.kwargs
        event_arg = call_kwargs["event"]
        assert isinstance(event_arg, ReviewEvent)
        assert event_arg.event_type == "ReviewCreated"
        assert event_arg.review_id == "11111111-1111-1111-1111-111111111111"


# ---------------------------------------------------------------------------
# 3 & 4. Unknown Event Types & Malformed Payload Handling
# ---------------------------------------------------------------------------
class TestMalformedAndUnknownEvents:
    """Verifies that poisonous or unrecognized messages do not crash the worker."""

    async def test_unknown_event_type_is_discarded_with_warning(
        self,
        mock_sqs_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        registry = EventHandlerRegistry()  # Empty registry
        consumer = SQSConsumer(sqs_client=mock_sqs_client, registry=registry)

        msg = {
            "MessageId": "msg-unknown-001",
            "ReceiptHandle": "receipt-unknown",
            "Body": json.dumps({"event_type": "UserDeleted", "user_id": "123"}),
        }

        with caplog.at_level(logging.WARNING):
            acknowledged = await consumer.process_single_message(msg, "http://queue-url")

        # Must acknowledge to discard message per explicit policy
        assert acknowledged is True
        mock_sqs_client.delete_message.assert_called_once_with(
            QueueUrl="http://queue-url",
            ReceiptHandle="receipt-unknown",
        )
        assert any("unrecognized or unsupported event_type 'userdeleted'" in rec.message.lower() for rec in caplog.records)

    async def test_malformed_json_body_is_discarded_with_error(
        self,
        mock_sqs_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        consumer = SQSConsumer(sqs_client=mock_sqs_client)
        msg = {
            "MessageId": "msg-malformed-001",
            "ReceiptHandle": "receipt-malformed",
            "Body": "{this is not valid json",
        }

        with caplog.at_level(logging.ERROR):
            acknowledged = await consumer.process_single_message(msg, "http://queue-url")

        assert acknowledged is True
        mock_sqs_client.delete_message.assert_called_once_with(
            QueueUrl="http://queue-url",
            ReceiptHandle="receipt-malformed",
        )
        assert any("malformed json" in rec.message.lower() for rec in caplog.records)

    async def test_invalid_schema_payload_is_discarded_with_error(
        self,
        mock_sqs_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        registry = EventHandlerRegistry()
        registry.register("ReviewCreated", AsyncMock())
        consumer = SQSConsumer(sqs_client=mock_sqs_client, registry=registry)

        # Missing required review_id
        msg = {
            "MessageId": "msg-invalid-schema-001",
            "ReceiptHandle": "receipt-invalid",
            "Body": json.dumps({"event_type": "ReviewCreated"}),
        }

        with caplog.at_level(logging.ERROR):
            acknowledged = await consumer.process_single_message(msg, "http://queue-url")

        assert acknowledged is True
        mock_sqs_client.delete_message.assert_called_once_with(
            QueueUrl="http://queue-url",
            ReceiptHandle="receipt-invalid",
        )
        assert any("validation failed" in rec.message.lower() for rec in caplog.records)


# ---------------------------------------------------------------------------
# 5 & 6. Message Acknowledgment vs. Redelivery on Failure
# ---------------------------------------------------------------------------
class TestMessageAcknowledgmentAndRedelivery:
    """Verifies that delete_message uses ReceiptHandle and occurs ONLY on success."""

    async def test_successful_processing_deletes_using_receipt_handle(
        self,
        mock_sqs_client: MagicMock,
        sample_sqs_message: dict[str, Any],
    ) -> None:
        registry = EventHandlerRegistry()
        registry.register("ReviewCreated", AsyncMock(return_value={"status": "processed"}))

        mock_session = AsyncMock(spec=AsyncSession)
        session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__.return_value = mock_session

        consumer = SQSConsumer(
            sqs_client=mock_sqs_client,
            registry=registry,
            session_factory=session_factory,
        )

        acknowledged = await consumer.process_single_message(sample_sqs_message, "http://queue-url")

        assert acknowledged is True
        # Must delete using ReceiptHandle, NEVER MessageId
        mock_sqs_client.delete_message.assert_called_once_with(
            QueueUrl="http://queue-url",
            ReceiptHandle="receipt-handle-abc-123",
        )

    async def test_handler_exception_does_not_delete_message(
        self,
        mock_sqs_client: MagicMock,
        sample_sqs_message: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Requirement 7: If the handler raises an exception, do not delete the message."""
        registry = EventHandlerRegistry()
        failing_handler = AsyncMock(side_effect=RuntimeError("Database connection lost during processing"))
        registry.register("ReviewCreated", failing_handler)

        mock_session = AsyncMock(spec=AsyncSession)
        session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__.return_value = mock_session

        consumer = SQSConsumer(
            sqs_client=mock_sqs_client,
            registry=registry,
            session_factory=session_factory,
        )

        with caplog.at_level(logging.ERROR):
            acknowledged = await consumer.process_single_message(sample_sqs_message, "http://queue-url")

        # Must return False and NEVER delete the message
        assert acknowledged is False
        mock_sqs_client.delete_message.assert_not_called()
        assert any("message not acknowledged; will be redelivered" in rec.message.lower() for rec in caplog.records)


# ---------------------------------------------------------------------------
# 7 & 8. Idempotent Event Processing
# ---------------------------------------------------------------------------
class TestIdempotency:
    """Verifies that duplicate event deliveries do not cause duplicate business actions."""

    async def test_duplicate_event_is_skipped(
        self,
        sample_film: Film,
    ) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        event = ReviewEvent(
            event_type="ReviewCreated",
            review_id=str(uuid.uuid4()),
            event_id="evt-duplicate-101",
        )

        # First call: event is NOT processed yet
        with patch.object(ProcessedEventDAO, "is_processed", new_callable=AsyncMock) as mock_is_proc:
            mock_is_proc.return_value = False
            with patch.object(ProcessedEventDAO, "record_event", new_callable=AsyncMock) as mock_rec:
                with patch("app.handlers.event_handlers.ReviewDAO") as mock_rdao_cls:
                    mock_rdao = AsyncMock()
                    mock_rdao.get_by_id.return_value = None
                    mock_rdao_cls.return_value = mock_rdao

                    res1 = await handle_review_created(event, mock_session)
                    assert res1["status"] == "processed"
                    mock_rec.assert_called_once()

        # Second call: event IS already processed
        with patch.object(ProcessedEventDAO, "is_processed", new_callable=AsyncMock) as mock_is_proc:
            mock_is_proc.return_value = True
            with patch.object(ProcessedEventDAO, "record_event", new_callable=AsyncMock) as mock_rec:
                res2 = await handle_review_created(event, mock_session)
                assert res2["status"] == "skipped"
                assert res2["reason"] == "already_processed"
                mock_rec.assert_not_called()

    async def test_concurrent_duplicate_delivery_catches_integrity_error(self) -> None:
        """Verifies database primary key constraint gracefully handles race conditions."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.flush.side_effect = IntegrityError("duplicate key value", params={}, orig=Exception())

        dao = ProcessedEventDAO(mock_session)
        result = await dao.record_event("evt-concurrent-duplicate", "ReviewCreated")

        # Returns None on duplicate constraint violation without raising unhandled exception
        assert result is None
        mock_session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# 9. Batch Processing Continues on Individual Failure
# ---------------------------------------------------------------------------
class TestBatchContinuation:
    """Verifies that an error in one message does not crash or abort remaining messages."""

    async def test_worker_continues_after_message_failure(
        self,
        mock_sqs_client: MagicMock,
    ) -> None:
        msg_fail = {
            "MessageId": "msg-fail",
            "ReceiptHandle": "handle-fail",
            "Body": json.dumps({"event_type": "ReviewCreated", "review_id": "bad-id"}),
        }
        msg_success = {
            "MessageId": "msg-success",
            "ReceiptHandle": "handle-success",
            "Body": json.dumps({"event_type": "ReviewCreated", "review_id": "good-id"}),
        }

        mock_sqs_client.receive_message.return_value = {"Messages": [msg_fail, msg_success]}

        consumer = SQSConsumer(sqs_client=mock_sqs_client)

        async def fake_process(msg: dict, queue_url: str) -> bool:
            if msg["MessageId"] == "msg-fail":
                return False
            consumer.acknowledge_message(queue_url, msg["ReceiptHandle"], msg["MessageId"])
            return True

        with patch.object(consumer, "process_single_message", side_effect=fake_process):
            count = await consumer.run_once()

        assert count == 2
        # Only the successful message was deleted
        mock_sqs_client.delete_message.assert_called_once_with(
            QueueUrl="http://localhost:4566/000000000000/review-events-queue",
            ReceiptHandle="handle-success",
        )


# ---------------------------------------------------------------------------
# 10. Failure Simulation for DLQ Redrive
# ---------------------------------------------------------------------------
class TestFailureSimulation:
    """Verifies isolated failure simulation raising SimulatedHandlerError."""

    async def test_simulated_failure_raises_and_prevents_deletion(
        self,
        mock_sqs_client: MagicMock,
        sample_sqs_message: dict[str, Any],
    ) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        session_factory = MagicMock(return_value=mock_session)
        mock_session.__aenter__.return_value = mock_session

        consumer = SQSConsumer(
            sqs_client=mock_sqs_client,
            session_factory=session_factory,
            simulate_failure=True,  # Test flag enabled
        )

        acknowledged = await consumer.process_single_message(sample_sqs_message, "http://queue-url")

        # Must NOT be acknowledged so SQS can redeliver and trigger DLQ
        assert acknowledged is False
        mock_sqs_client.delete_message.assert_not_called()
