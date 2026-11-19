import logging
import uuid
from typing import Any, Protocol, runtime_checkable

import boto3
from botocore.exceptions import ClientError

from app.core.config import Settings, settings
from app.schemas.event import ReviewEvent

logger = logging.getLogger("event_publisher")


@runtime_checkable
class EventPublisher(Protocol):
    def publish_review_event(self, event_type: str, review_id: str, event_id: str | None = None) -> None:
        """Publish a review event (ReviewCreated or ReviewUpdated)."""
        ...
    def check_queue_health(self) -> bool:
        """Check if the queue is reachable at startup. Does not raise exceptions."""
        ...


class SQSEventPublisher:
    """
    SQS implementation of the EventPublisher interface using Boto3.
    Publishes lightweight review lifecycle events to the review events SQS queue.
    """

    def __init__(self, cfg: Settings | None = None, sqs_client: Any | None = None) -> None:
        self.settings = cfg or settings
        self.queue_name = self.settings.SQS_QUEUE_NAME
        self._queue_url: str | None = None
        self._sqs_client: Any = sqs_client

    @property
    def client(self) -> Any:
        if self._sqs_client is None:
            self._sqs_client = boto3.client(
                "sqs",
                region_name=self.settings.AWS_REGION or self.settings.AWS_DEFAULT_REGION,
                aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY,
                endpoint_url=self.settings.SQS_ENDPOINT_URL or self.settings.AWS_ENDPOINT_URL,
            )
        return self._sqs_client

    def get_queue_url(self) -> str | None:
        """
        Get or resolve the SQS queue URL, creating it in Floci if it does not exist.
        Caches the URL on success. Returns None if unreachable.
        """
        if self._queue_url:
            return self._queue_url

        try:
            resp = self.client.get_queue_url(QueueName=self.queue_name)
            self._queue_url = resp["QueueUrl"] #{"QueueUrl": "http://localhost:4566/000000000000/review-events-queue", ...}
            return self._queue_url
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "") 
            if code in ("QueueDoesNotExist", "AWS.SimpleQueueService.NonExistentQueue"):
                try:
                    create_resp = self.client.create_queue(QueueName=self.queue_name)
                    self._queue_url = create_resp["QueueUrl"]
                    logger.info("Created SQS queue: %s (url: %s)", self.queue_name, self._queue_url)
                    return self._queue_url
                except Exception as create_exc:
                    logger.error("Failed to create SQS queue %s: %s", self.queue_name, create_exc)
                    return None
            logger.error("Failed to resolve SQS queue URL for %s: %s", self.queue_name, exc)
            return None
        except Exception as exc:
            logger.error("Failed to connect to SQS service: %s", exc)
            return None

    def check_queue_health(self) -> bool:
        """
        Application startup check.
        Checks whether SQS / Floci queue is reachable.
        If unavailable, logs a clear warning without crashing the application.
        """
        try:
            url = self.get_queue_url()
            if url:
                logger.info("SQS queue '%s' is reachable at %s", self.queue_name, url)
                return True
            logger.warning(
                "SQS queue '%s' is currently unreachable or could not be resolved. Application will continue without event publishing.",
                self.queue_name,
            )
            return False
        except Exception as exc:
            logger.warning(
                "SQS queue '%s' check failed during startup: %s. Application will continue.",
                self.queue_name,
                exc,
            )
            return False

    def publish_review_event(self, event_type: str, review_id: str, event_id: str | None = None) -> None:
        """
        Publish a typed review event to SQS.
        Serializes payload containing event_type, review_id, timestamp, and stable event_id.
        Catches publishing errors, logs them, and does not crash the request flow.
        """
        try:
            # 1. Build typed Pydantic event payload
            resolved_event_id = event_id or str(uuid.uuid4())
            event = ReviewEvent(
                event_type=event_type,  # type: ignore[arg-type]
                review_id=str(review_id),
                event_id=resolved_event_id,
            )
            payload_json = event.model_dump_json()

            # 2. Resolve queue URL
            queue_url = self.get_queue_url()
            if not queue_url:
                logger.error(
                    "Cannot publish event '%s' for review %s: SQS queue '%s' is unavailable",
                    event_type,
                    review_id,
                    self.queue_name,
                )
                return

            # 3. Publish message to SQS
            self.client.send_message(
                QueueUrl=queue_url,
                MessageBody=payload_json,
            )
            logger.info(
                "Successfully published '%s' event for review %s to SQS queue %s",
                event_type,
                review_id,
                self.queue_name,
            )
        except Exception as exc:
            logger.error(
                "Failed to publish '%s' event for review %s: %s",
                event_type,
                review_id,
                exc,
                exc_info=True,
            )

