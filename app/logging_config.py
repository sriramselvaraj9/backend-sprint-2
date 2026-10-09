import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# ==============================================================================
# Automatic Request Tracking via ContextVar
# ==============================================================================
request_id_ctx: ContextVar[str | None] = ContextVar("request_id_ctx", default=None)


def get_current_request_id() -> str | None:
    return request_id_ctx.get()


def set_current_request_id(request_id: str | None) -> Any:
    return request_id_ctx.set(request_id)


# ==============================================================================
# Structured JSON Logs for Production & Easy Debugging
# ==============================================================================
class StructuredJsonFormatter(logging.Formatter):
    """
    Converts log records into standard JSON objects with ISO-8601 timestamps
    and the request-scoped trace ID.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_timestamp = datetime.fromtimestamp(record.created, tz=UTC).isoformat()

        log_data: dict[str, Any] = {
            "level": record.levelname,
            "timestamp": log_timestamp,
            "logger": record.name,
            "message": record.getMessage(),
        }

        req_id = get_current_request_id()
        if not req_id:
            req_id = getattr(record, "request_id", None)

        if req_id:
            log_data["request_id"] = req_id

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Configure application-wide structured JSON logging.
    Attaches a StreamHandler with StructuredJsonFormatter to the root logger.
    """
    level_val = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level_val)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level_val)
    handler.setFormatter(StructuredJsonFormatter())
    root_logger.addHandler(handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Convenience factory to obtain a logger with the given name.
    """
    return logging.getLogger(name)
