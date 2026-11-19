"""
tests/integration/test_worker_dlq_integration.py

Integration tests for SQS standalone consumer, DLQ configuration, and RedrivePolicy.
Executes against local Floci emulator and isolated SQLite test database.
"""

import asyncio
import json
import time
import uuid

import boto3
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.core.database
import app.core.redis
from app.core.config import Settings, settings
from app.models.film import Film
from app.models.processed_event import ProcessedEvent
from app.models.review import Review
from app.models.user import User
from app.services.sqs_consumer import SQSConsumer, setup_queue_and_dlq

pytestmark = pytest.mark.integration


@pytest.fixture
def floci_sqs_client() -> boto3.client:
    """Live Boto3 client pointing to local Floci SQS emulator."""
    endpoint_url = settings.SQS_ENDPOINT_URL or settings.AWS_ENDPOINT_URL or "http://localhost:4566"
    return boto3.client(
        "sqs",
        endpoint_url=endpoint_url,
        region_name=settings.AWS_REGION or settings.AWS_DEFAULT_REGION or "us-east-1",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or "test",
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or "test",
    )


class TestWorkerDLQIntegration:
    """Integration test suite verifying DLQ setup, RedrivePolicy, and end-to-end event processing."""

    def test_setup_queue_and_dlq_configuration(self, floci_sqs_client: boto3.client) -> None:
        """
        Verify that setup_queue_and_dlq safely configures the source queue and DLQ in Floci
        with correct RedrivePolicy and maxReceiveCount.
        """
        custom_cfg = Settings(
            SQS_QUEUE_NAME=f"test-main-{uuid.uuid4().hex[:6]}",
            SQS_DLQ_NAME=f"test-dlq-{uuid.uuid4().hex[:6]}",
            SQS_MAX_RECEIVE_COUNT=3,
            SQS_VISIBILITY_TIMEOUT=15,
            ACCESS_TOKEN_EXPIRE_MINUTES=30,
            REFRESH_TOKEN_EXPIRE_DAYS=7,
            ALLOWED_CORS_ORIGINS="http://localhost:3000",
            API_VERSION="v1",
        )

        result = setup_queue_and_dlq(floci_sqs_client, custom_cfg)
        main_url = result["main_url"]
        dlq_url = result["dlq_url"]
        dlq_arn = result["dlq_arn"]

        assert main_url is not None
        assert dlq_url is not None
        assert dlq_arn.startswith("arn:aws:sqs:")

        # Verify attributes on source queue
        attrs = floci_sqs_client.get_queue_attributes(
            QueueUrl=main_url,
            AttributeNames=["RedrivePolicy", "VisibilityTimeout"],
        )["Attributes"]

        assert attrs["VisibilityTimeout"] == "15"
        policy = json.loads(attrs["RedrivePolicy"])
        assert policy["deadLetterTargetArn"] == dlq_arn
        assert policy["maxReceiveCount"] == "3"

    async def test_end_to_end_worker_event_consumption(
        self,
        floci_sqs_client: boto3.client,
        db_session: AsyncSession,
        test_session_factory: async_sessionmaker[AsyncSession],
        fake_redis,
        monkeypatch: pytest.MonkeyPatch,
        create_user,
    ) -> None:
        """
        End-to-End Processing Test:
        1. Seed Film and Review in database.
        2. Publish ReviewCreated event to Floci SQS queue.
        3. Execute consumer.run_once().
        4. Confirm message was processed and deleted from SQS.
        5. Confirm ProcessedEvent record was written.
        6. Confirm denormalized Film review_count and average_rating were updated.
        """
        monkeypatch.setattr(app.core.database, "SessionLocal", test_session_factory)
        monkeypatch.setattr(app.core.redis, "redis_client", fake_redis)

        queue_name = f"test-e2e-{uuid.uuid4().hex[:6]}"
        dlq_name = f"test-e2e-dlq-{uuid.uuid4().hex[:6]}"
        custom_cfg = Settings(
            SQS_QUEUE_NAME=queue_name,
            SQS_DLQ_NAME=dlq_name,
            SQS_MAX_RECEIVE_COUNT=3,
            SQS_VISIBILITY_TIMEOUT=30,
            SQS_WAIT_TIME_SECONDS=2,
            ACCESS_TOKEN_EXPIRE_MINUTES=30,
            REFRESH_TOKEN_EXPIRE_DAYS=7,
            ALLOWED_CORS_ORIGINS="http://localhost:3000",
            API_VERSION="v1",
        )

        setup_result = setup_queue_and_dlq(floci_sqs_client, custom_cfg)
        queue_url = setup_result["main_url"]

        # 1. Seed database with Film and Review
        author: User = await create_user(username="film_critic_1", email="critic1@example.com")
        film = Film(
            id=uuid.uuid4(),
            title="Oppenheimer",
            release_year=2023,
            genre="Biography",
            director="Christopher Nolan",
            review_count=0,
            average_rating=None,
        )
        db_session.add(film)
        await db_session.commit()

        review = Review(
            id=uuid.uuid4(),
            film_id=film.id,
            user_id=author.id,
            rating=10,
            body="Masterful filmmaking and storytelling.",
        )
        db_session.add(review)
        await db_session.commit()

        # 2. Publish ReviewCreated event to SQS queue
        event_id = f"evt-{uuid.uuid4().hex}"
        event_payload = {
            "event_type": "ReviewCreated",
            "review_id": str(review.id),
            "event_id": event_id,
            "timestamp": "2026-11-17T12:00:00Z",
        }
        floci_sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(event_payload),
        )

        # 3. Create consumer and run single polling pass
        consumer = SQSConsumer(
            cfg=custom_cfg,
            sqs_client=floci_sqs_client,
            session_factory=test_session_factory,
        )
        processed_count = await consumer.run_once()
        assert processed_count == 1

        # 4. Verify message was acknowledged and removed from queue
        poll_check = floci_sqs_client.receive_message(
            QueueUrl=queue_url,
            WaitTimeSeconds=1,
            MaxNumberOfMessages=1,
        )
        assert len(poll_check.get("Messages", [])) == 0

        # 5. Verify ProcessedEvent was recorded in DB
        async with test_session_factory() as verify_session:
            stmt = select(ProcessedEvent).where(ProcessedEvent.event_id == event_id)
            result = await verify_session.execute(stmt)
            event_rec = result.scalar_one_or_none()
            assert event_rec is not None
            assert event_rec.event_type == "ReviewCreated"
            assert event_rec.review_id == str(review.id)

            # 6. Verify Film aggregates were updated by the worker handler
            refreshed_film = await verify_session.get(Film, film.id)
            assert refreshed_film is not None
            assert refreshed_film.review_count == 1
            assert refreshed_film.average_rating == 10.0

    async def test_worker_dlq_redrive_on_repeated_failure(
        self,
        floci_sqs_client: boto3.client,
        test_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """
        DLQ Redrive Verification:
        1. Configure queue with maxReceiveCount=2 and short VisibilityTimeout=1s.
        2. Send a review event message.
        3. Run worker with simulate_failure=True twice.
        4. Confirm message was not deleted.
        5. Verify that after maxReceiveCount is exceeded, message moves to DLQ.
        """
        queue_name = f"test-fail-{uuid.uuid4().hex[:6]}"
        dlq_name = f"test-fail-dlq-{uuid.uuid4().hex[:6]}"
        custom_cfg = Settings(
            SQS_QUEUE_NAME=queue_name,
            SQS_DLQ_NAME=dlq_name,
            SQS_MAX_RECEIVE_COUNT=2,
            SQS_VISIBILITY_TIMEOUT=1,
            SQS_WAIT_TIME_SECONDS=1,
            ACCESS_TOKEN_EXPIRE_MINUTES=30,
            REFRESH_TOKEN_EXPIRE_DAYS=7,
            ALLOWED_CORS_ORIGINS="http://localhost:3000",
            API_VERSION="v1",
        )

        setup_result = setup_queue_and_dlq(floci_sqs_client, custom_cfg)
        main_url = setup_result["main_url"]
        dlq_url = setup_result["dlq_url"]

        # Send test message
        event_payload = {
            "event_type": "ReviewCreated",
            "review_id": str(uuid.uuid4()),
            "event_id": f"evt-fail-{uuid.uuid4().hex[:6]}",
        }
        floci_sqs_client.send_message(
            QueueUrl=main_url,
            MessageBody=json.dumps(event_payload),
        )

        # Consumer with simulated failure enabled
        consumer = SQSConsumer(
            cfg=custom_cfg,
            sqs_client=floci_sqs_client,
            session_factory=test_session_factory,
            simulate_failure=True,
        )

        # First receive & fail (receive count = 1)
        count1 = await consumer.run_once()
        assert count1 == 1

        # Wait for 1s visibility timeout to expire
        await asyncio.sleep(1.5)

        # Second receive & fail (receive count = 2 -> threshold reached)
        count2 = await consumer.run_once()
        assert count2 == 1

        # Wait for 1s visibility timeout to expire
        await asyncio.sleep(1.5)

        # Third poll: SQS redrives message to DLQ because maxReceiveCount (2) was reached
        count3 = await consumer.run_once()
        assert count3 == 0

        # Wait for Floci redrive processing
        await asyncio.sleep(1.0)

        # 5. Check DLQ: message must be present in DLQ
        dlq_resp = floci_sqs_client.receive_message(
            QueueUrl=dlq_url,
            WaitTimeSeconds=2,
            MaxNumberOfMessages=1,
        )
        dlq_messages = dlq_resp.get("Messages", [])
        assert len(dlq_messages) == 1, "Expected message to move to DLQ after exceeding maxReceiveCount"

        dlq_body = json.loads(dlq_messages[0]["Body"])
        assert dlq_body["event_type"] == "ReviewCreated"
        assert dlq_body["event_id"] == event_payload["event_id"]
