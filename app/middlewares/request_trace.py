import uuid

from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import set_current_request_id


async def request_trace_logging_middleware(request: Request, call_next) -> Response:
    """
    Middleware that intercepts incoming requests, attaches or generates a unique
    X-Request-ID for distributed tracing, stores it in async ContextVar memory,
    and attaches it to the outgoing response headers.
    """
    # 1. Get existing trace header or generate a new UUID
    req_id = request.headers.get("X-Request-ID") or request.headers.get("X-Trace-ID") or str(uuid.uuid4())

    # 2. Store in async memory (ContextVar)
    set_current_request_id(req_id)

    try:
        # 3. Send request forward to the Route Handler
        response = await call_next(request)

        # 4. On the way out, stamp trace ID onto outgoing response header
        response.headers["X-Request-ID"] = req_id
        return response
    finally:
        # 5. Reset memory to clean up
        set_current_request_id(None)
