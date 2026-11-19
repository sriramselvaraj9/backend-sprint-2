import asyncio
import json
import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings, settings
from app.core.database import SessionLocal
from app.handlers.event_handlers import (
    EventHandlerRegistry,
    SimulatedHandlerError,
    event_registry,
)
from app.schemas.event import ReviewEvent

logger = logging.getLogger("sqs_consumer")


def setup_queue_and_dlq(sqs_client: Any, cfg: Settings | None = None) -> dict[str, str]:
    """
    Ensure the main SQS queue and Dead-Letter Queue (DLQ) are created and configured.
    Sets RedrivePolicy on the main queue with deadLetterTargetArn and maxReceiveCount.
    Safe and repeatable to run multiple times.
    """
    config = cfg or settings
    queue_name = config.SQS_QUEUE_NAME or "review-events-queue"
    dlq_name = config.SQS_DLQ_NAME or "review-events-dlq"
    max_receive_count = config.SQS_MAX_RECEIVE_COUNT
    visibility_timeout = config.SQS_VISIBILITY_TIMEOUT

    # 1. Create or get DLQ
    try:
        dlq_res = sqs_client.create_queue(QueueName=dlq_name)
        dlq_url = dlq_res["QueueUrl"]
    except ClientError:
        dlq_url = sqs_client.get_queue_url(QueueName=dlq_name)["QueueUrl"]

    # 2. Get DLQ ARN
    dlq_attrs = sqs_client.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])
    dlq_arn = dlq_attrs["Attributes"]["QueueArn"]
    logger.info("Configured DLQ: %s (ARN: %s)", dlq_name, dlq_arn)

    # 3. Create or get main queue
    try:
        main_res = sqs_client.create_queue(QueueName=queue_name)
        main_url = main_res["QueueUrl"]
    except ClientError:
        main_url = sqs_client.get_queue_url(QueueName=queue_name)["QueueUrl"]

    # 4. Attach RedrivePolicy and VisibilityTimeout to main queue
    redrive_policy = {
        "deadLetterTargetArn": dlq_arn,
        "maxReceiveCount": str(max_receive_count),
    }
    sqs_client.set_queue_attributes(
        QueueUrl=main_url,
        Attributes={
            "RedrivePolicy": json.dumps(redrive_policy),
            "VisibilityTimeout": str(visibility_timeout),
        },
    )
    logger.info(
        "Attached RedrivePolicy to '%s' -> DLQ '%s' (maxReceiveCount=%d, visibilityTimeout=%d)",
        queue_name,
        dlq_name,
        max_receive_count,
        visibility_timeout,
    )

    return {"main_url": main_url, "dlq_url": dlq_url, "dlq_arn": dlq_arn}


class SQSConsumer:
    """
    Standalone SQS long-polling consumer process.
    Consumes review lifecycle events, routes them to handlers, enforces idempotency,
    and acknowledges messages only upon successful processing.
    """

    def __init__(
        self,
        cfg: Settings | None = None,
        sqs_client: Any | None = None,
        registry: EventHandlerRegistry | None = None,
        session_factory: async_sessionmaker | None = None,
        simulate_failure: bool = False,
    ) -> None:
        self.settings = cfg or settings
        self.queue_name = self.settings.SQS_QUEUE_NAME or "review-events-queue"
        self._sqs_client = sqs_client
        self._queue_url: str | None = None
        self.registry = registry or event_registry
        self.session_factory = session_factory or SessionLocal
        self.simulate_failure = simulate_failure or self.settings.SIMULATE_HANDLER_FAILURE
        self.should_stop = False

    @property
    def client(self) -> Any:
        if self._sqs_client is None:
            self._sqs_client = boto3.client(
                "sqs",
                region_name=self.settings.AWS_REGION or self.settings.AWS_DEFAULT_REGION or "us-east-1",
                aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID or "test",
                aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY or "test",
                endpoint_url=self.settings.SQS_ENDPOINT_URL or self.settings.AWS_ENDPOINT_URL,
            )
        return self._sqs_client

    def get_queue_url(self) -> str:
        """Resolve or configure the SQS queue URL."""
        if self._queue_url:
            return self._queue_url

        try:
            resp = self.client.get_queue_url(QueueName=self.queue_name)
            self._queue_url = resp["QueueUrl"]
            return self._queue_url
        except ClientError:
            # Setup main queue and DLQ with RedrivePolicy
            result = setup_queue_and_dlq(self.client, self.settings)
            self._queue_url = result["main_url"]
            return self._queue_url

    def acknowledge_message(self, queue_url: str, receipt_handle: str, message_id: str) -> None:
        """
        Delete an acknowledged message from the SQS queue using its ReceiptHandle.
        Never uses MessageId for deletion.
        """
        self.client.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
        )
        logger.info("Acknowledged and deleted message %s from queue %s", message_id, self.queue_name)

    async def process_single_message(self, message: dict[str, Any], queue_url: str) -> bool:
        """
        Process a single SQS message:
        1. Deserializes JSON and validates payload.
        2. Routes to handler using handler registry.
        3. Enforces idempotency and executes business work.
        4. Acknowledges message with ReceiptHandle ONLY on success.
        Returns True if acknowledged/discarded, False if failed (left for redelivery).
        """
        message_id = message.get("MessageId", "unknown")
        receipt_handle = message.get("ReceiptHandle", "")
        body_raw = message.get("Body", "")

        logger.info("Processing SQS message %s (ReceiptHandle: %s...)", message_id, receipt_handle[:20])

        # 1. Parse JSON body
        try:
            body_dict = json.loads(body_raw)
        except json.JSONDecodeError as exc:
            logger.error(
                "Malformed JSON in message %s body: %s. Discarding poisonous message to avoid loop.",
                message_id,
                exc,
            )
            # Discard malformed JSON so it doesn't loop
            self.acknowledge_message(queue_url, receipt_handle, message_id)
            return True

        if not isinstance(body_dict, dict):
            logger.error("Message %s body is not a JSON object. Discarding message.", message_id)
            self.acknowledge_message(queue_url, receipt_handle, message_id)
            return True

        event_type = body_dict.get("event_type")

        # 2. Check for unrecognized event type
        if not event_type or not self.registry.is_supported(event_type):
            logger.warning(
                "Unrecognized or unsupported event_type '%s' in message %s. Discarding message according to explicit policy.",
                event_type,
                message_id,
            )
            # Acknowledge to avoid endless retries of unsupported events
            self.acknowledge_message(queue_url, receipt_handle, message_id)
            return True

        # 3. Deserialize and validate typed event schema
        try:
            event = ReviewEvent.model_validate(body_dict)
        except ValidationError as val_err:
            logger.error(
                "Payload validation failed for message %s (event_type: %s): %s. Discarding invalid payload.",
                message_id,
                event_type,
                val_err,
            )
            self.acknowledge_message(queue_url, receipt_handle, message_id)
            return True

        # Fallback to message_id if event_id is omitted
        if not event.event_id:
            event.event_id = message_id

        # 4. Route to registered handler
        handler = self.registry.get_handler(event.event_type)
        if handler is None:
            logger.warning("No handler found for event type '%s'. Discarding message.", event.event_type)
            self.acknowledge_message(queue_url, receipt_handle, message_id)
            return True

        # 5. Execute handler in an isolated database session
        try:
            async with self.session_factory() as session:
                result = await handler(
                    event=event,
                    session=session,
                    simulate_failure=self.simulate_failure,
                )
                logger.info(
                    "Handler for '%s' completed successfully on message %s (result: %s)",
                    event.event_type,
                    message_id,
                    result.get("status"),
                )

            # 6. Acknowledge message using ReceiptHandle ONLY after successful processing
            self.acknowledge_message(queue_url, receipt_handle, message_id)
            return True

        except SimulatedHandlerError as sim_err:
            logger.error(
                "Simulated failure in handler for message %s: %s. Message NOT deleted to allow SQS redelivery and DLQ testing.",
                message_id,
                sim_err,
            )
            return False

        except Exception as exc:
            logger.error(
                "Unhandled error processing message %s (event_type: %s): %s. Message NOT acknowledged; will be redelivered.",
                message_id,
                event.event_type,
                exc,
                exc_info=True,
            )
            # DO NOT acknowledge; message visibility timeout will expire and SQS will redeliver
            return False

    async def poll_batch(self, queue_url: str) -> list[dict[str, Any]]:
        """
        Poll SQS using long polling with WaitTimeSeconds.
        Returns list of received messages.
        """
        max_messages = min(self.settings.SQS_MAX_NUMBER_OF_MESSAGES, 10)
        wait_seconds = self.settings.SQS_WAIT_TIME_SECONDS

        try:
            response = await asyncio.to_thread(
                self.client.receive_message,
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_seconds,
                VisibilityTimeout=self.settings.SQS_VISIBILITY_TIMEOUT,
                AttributeNames=["All"],
                MessageAttributeNames=["All"],
            )
            return response.get("Messages", [])
        except ClientError as exc:
            logger.error("Error receiving messages from SQS queue %s: %s", self.queue_name, exc)
            return []
        except Exception as exc:
            logger.error("Unexpected connection error during SQS receive_message: %s", exc)
            return []

    async def run_once(self) -> int:
        """
        Execute a single polling iteration and process received messages.
        Returns number of messages received.
        """
        queue_url = self.get_queue_url()
        messages = await self.poll_batch(queue_url)
        if not messages:
            logger.debug("No messages received during poll cycle.")
            return 0

        logger.info("Received %d message(s) from queue %s", len(messages), self.queue_name)
        for msg in messages:
            try:
                await self.process_single_message(msg, queue_url)
            except Exception as exc:
                logger.error("Unexpected error in message processing loop for %s: %s", msg.get("MessageId"), exc)

        return len(messages)

    async def start(self, stop_event: asyncio.Event | None = None) -> None:
        """
        Continuous consumer loop.
        Polls SQS queue until stop_event is set or self.should_stop is True.
        """
        logger.info("Starting SQS consumer worker for queue '%s'", self.queue_name)
        queue_url = self.get_queue_url()
        logger.info("SQS Consumer connected to queue URL: %s", queue_url)

        while not self.should_stop:
            if stop_event and stop_event.is_set():
                logger.info("Stop event signaled. Exiting SQS consumer loop.")
                break

            try:
                await self.run_once()
            except asyncio.CancelledError:
                logger.info("Consumer loop cancelled.")
                break
            except Exception as exc:
                logger.error("Error in consumer polling loop: %s. Continuing...", exc, exc_info=True)
                await asyncio.sleep(1)

        logger.info("SQS consumer worker stopped cleanly.")

    def stop(self) -> None:
        """Signal consumer to stop gracefully."""
        self.should_stop = True
