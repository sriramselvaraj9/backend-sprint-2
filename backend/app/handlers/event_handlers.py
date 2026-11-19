import logging
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.film_cache import FilmCache
from app.core.config import settings
from app.core.redis import redis_client
from app.daos.film_dao import FilmDAO
from app.daos.processed_event_dao import ProcessedEventDAO
from app.daos.review_dao import ReviewDAO
from app.schemas.event import ReviewEvent
from app.services.film_service import FilmService

logger = logging.getLogger("event_handlers")


class SimulatedHandlerError(RuntimeError):
    """Exception raised exclusively for DLQ redrive and retry failure simulation."""
    pass


EventHandlerFunc = Callable[..., Coroutine[Any, Any, dict[str, Any]]]


class EventHandlerRegistry:
    """
    Registry for routing typed events to their dedicated business handlers.
    Decoupled from FastAPI routes and HTTP concerns.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, EventHandlerFunc] = {}

    def register(self, event_type: str, handler: EventHandlerFunc) -> None:
        """Register an async handler function for an event_type."""
        self._handlers[event_type] = handler
        logger.debug("Registered handler for event type: %s", event_type)

    def get_handler(self, event_type: str) -> EventHandlerFunc | None:
        """Retrieve the handler registered for the given event_type, or None if unknown."""
        return self._handlers.get(event_type)

    def is_supported(self, event_type: str) -> bool:
        """Check whether an event_type has a registered handler."""
        return event_type in self._handlers


# Global default registry instance
event_registry = EventHandlerRegistry()


async def handle_review_created(
    event: ReviewEvent,
    session: AsyncSession,
    simulate_failure: bool = False,
) -> dict[str, Any]:
    """
    Handler for ReviewCreated events.
    1. Enforces idempotency via ProcessedEventDAO.
    2. Recalculates denormalized film aggregates (review_count, average_rating).
    3. Atomically commits business updates and processed-event record.
    """
    if simulate_failure or settings.SIMULATE_HANDLER_FAILURE:
        logger.warning(
            "SIMULATED FAILURE triggered for ReviewCreated event (review_id: %s)",
            event.review_id,
        )
        raise SimulatedHandlerError(f"Simulated failure for ReviewCreated (review_id: {event.review_id})")

    event_id = event.event_id or f"ReviewCreated:{event.review_id}:{event.timestamp}"
    processed_dao = ProcessedEventDAO(session)

    # Idempotency check
    if await processed_dao.is_processed(event_id):
        logger.info(
            "Event '%s' (type: ReviewCreated, review_id: %s) already processed. Skipping business effects.",
            event_id,
            event.review_id,
        )
        return {"status": "skipped", "reason": "already_processed", "event_id": event_id}

    # Fetch review to identify target film
    review_dao = ReviewDAO(session)
    film_dao = FilmDAO(session)
    review_uid = uuid.UUID(event.review_id)
    review = await review_dao.get_by_id(review_uid)

    if review is not None:
        film_service = FilmService(
            film_dao=film_dao,
            review_dao=review_dao,
            cache=FilmCache(redis_client),
        )
        await film_service.recalculate_film_review_aggregates(review.film_id)
        logger.info(
            "Recalculated film review aggregates for film %s triggered by review %s",
            review.film_id,
            event.review_id,
        )
    else:
        logger.warning(
            "Review '%s' referenced in ReviewCreated event was not found in database",
            event.review_id,
        )

    # Persist processed record atomically
    await processed_dao.record_event(
        event_id=event_id,
        event_type="ReviewCreated",
        review_id=event.review_id,
        status="PROCESSED",
    )
    await session.commit()

    return {"status": "processed", "event_id": event_id, "review_id": event.review_id}


async def handle_review_updated(
    event: ReviewEvent,
    session: AsyncSession,
    simulate_failure: bool = False,
) -> dict[str, Any]:
    """
    Handler for ReviewUpdated events.
    1. Enforces idempotency via ProcessedEventDAO.
    2. Recalculates denormalized film aggregates (review_count, average_rating).
    3. Atomically commits business updates and processed-event record.
    """
    if simulate_failure or settings.SIMULATE_HANDLER_FAILURE:
        logger.warning(
            "SIMULATED FAILURE triggered for ReviewUpdated event (review_id: %s)",
            event.review_id,
        )
        raise SimulatedHandlerError(f"Simulated failure for ReviewUpdated (review_id: {event.review_id})")

    event_id = event.event_id or f"ReviewUpdated:{event.review_id}:{event.timestamp}"
    processed_dao = ProcessedEventDAO(session)

    # Idempotency check
    if await processed_dao.is_processed(event_id):
        logger.info(
            "Event '%s' (type: ReviewUpdated, review_id: %s) already processed. Skipping business effects.",
            event_id,
            event.review_id,
        )
        return {"status": "skipped", "reason": "already_processed", "event_id": event_id}

    # Fetch review to identify target film
    review_dao = ReviewDAO(session)
    film_dao = FilmDAO(session)
    review_uid = uuid.UUID(event.review_id)
    review = await review_dao.get_by_id(review_uid)

    if review is not None:
        film_service = FilmService(
            film_dao=film_dao,
            review_dao=review_dao,
            cache=FilmCache(redis_client),
        )
        await film_service.recalculate_film_review_aggregates(review.film_id)
        logger.info(
            "Recalculated film review aggregates for film %s triggered by updated review %s",
            review.film_id,
            event.review_id,
        )
    else:
        logger.warning(
            "Review '%s' referenced in ReviewUpdated event was not found in database",
            event.review_id,
        )

    # Persist processed record atomically
    await processed_dao.record_event(
        event_id=event_id,
        event_type="ReviewUpdated",
        review_id=event.review_id,
        status="PROCESSED",
    )
    await session.commit()

    return {"status": "processed", "event_id": event_id, "review_id": event.review_id}


# Register supported handlers with the default registry
event_registry.register("ReviewCreated", handle_review_created)
event_registry.register("ReviewUpdated", handle_review_updated)
