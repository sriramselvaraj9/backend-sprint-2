"""
backend/worker.py

Dedicated standalone event consumer worker entry point.
Consumes review lifecycle events from SQS independently of the FastAPI web application.
Does not import FastAPI routes, route handlers, or API-specific web services.
"""

import asyncio
import logging
import signal
import sys
from typing import Any

from app.core.config import settings
from app.core.database import engine, init_db
from app.core.redis import redis_client
from app.logging_config import setup_logging
from app.services.sqs_consumer import SQSConsumer

# Setup structured JSON logging
setup_logging()
logger = logging.getLogger("worker")


class StandaloneWorker:
    """
    Manages the lifecycle, signal handling, and execution of the standalone SQS consumer worker.
    """

    def __init__(self) -> None:
        self.stop_event = asyncio.Event()
        self.consumer = SQSConsumer(cfg=settings)

    def _setup_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown on SIGINT and SIGTERM."""
        loop = asyncio.get_running_loop()

        def signal_handler(sig_name: str) -> None:
            logger.info("Received termination signal %s. Initiating graceful shutdown...", sig_name)
            self.consumer.stop()
            self.stop_event.set()

        # On Windows, signal handlers can be attached via signal.signal
        if sys.platform == "win32":
            signal.signal(signal.SIGINT, lambda s, f: signal_handler("SIGINT"))
            signal.signal(signal.SIGTERM, lambda s, f: signal_handler("SIGTERM"))
        else:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, signal_handler, sig.name)

    async def run(self) -> None:
        """
        Execute worker startup, schema readiness, consumer loop, and clean disposal.
        """
        logger.info("=========================================================")
        logger.info("   Starting Standalone Film Review Event Consumer Worker ")
        logger.info("   Queue: %s | DLQ: %s", settings.SQS_QUEUE_NAME, settings.SQS_DLQ_NAME)
        logger.info("   Simulate Failure Mode: %s", settings.SIMULATE_HANDLER_FAILURE)
        logger.info("=========================================================")

        # 1. Ensure required database tables exist (e.g., processed_events)
        try:
            logger.info("Ensuring database schema readiness...")
            await init_db()
            logger.info("Database schema initialized successfully.")
        except Exception as exc:
            logger.error("Failed to initialize database schema: %s", exc, exc_info=True)
            raise

        # 2. Attach signal handlers
        self._setup_signal_handlers()

        # 3. Start consumer loop
        try:
            await self.consumer.start(stop_event=self.stop_event)
        except Exception as exc:
            logger.error("Fatal error in worker consumer loop: %s", exc, exc_info=True)
        finally:
            # 4. Graceful disposal of shared resources
            logger.info("Worker shutting down - disposing database engine connection pool...")
            await engine.dispose()
            logger.info("Worker shutting down - closing Redis client connection pool...")
            await redis_client.aclose()
            logger.info("Standalone Event Consumer Worker shutdown completed cleanly.")


def main() -> None:
    """Entry point for standalone worker process."""
    worker = StandaloneWorker()
    try:
        asyncio.run(worker.run())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker process terminated.")


if __name__ == "__main__":
    main()
