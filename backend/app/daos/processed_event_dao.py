import logging
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.processed_event import ProcessedEvent

logger = logging.getLogger("processed_event_dao")


class ProcessedEventDAO:
    """
    Data Access Object for persistent event idempotency tracking.
    Enforces uniqueness using a database primary key constraint to prevent duplicate processing.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, event_id: str) -> ProcessedEvent | None:
        """Query a processed event record by its unique event_id."""
        stmt = select(ProcessedEvent).where(ProcessedEvent.event_id == event_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def is_processed(self, event_id: str) -> bool:
        """Check whether an event with the given ID has already been recorded."""
        record = await self.get_by_id(event_id)
        return record is not None

    async def record_event(
        self,
        event_id: str,
        event_type: str,
        review_id: str | None = None,
        status: str = "PROCESSED",
    ) -> ProcessedEvent | None:
        """
        Record that an event has been processed.
        Returns the ProcessedEvent on success, or None if a duplicate entry exists.
        """
        record = ProcessedEvent(
            event_id=event_id,
            event_type=event_type,
            review_id=review_id,
            status=status,
        )
        try:
            self.session.add(record)
            await self.session.flush()
            return record
        except IntegrityError:
            await self.session.rollback()
            logger.info("Duplicate event '%s' detected via primary key constraint", event_id)
            return None
