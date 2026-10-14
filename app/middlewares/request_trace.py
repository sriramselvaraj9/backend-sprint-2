import time
import uuid

from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import reset_request_id, set_request_id


async def request_id_middleware(request: Request, call_next) -> Response:
    start_time = time.perf_counter()
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())  # generate new id if not present
    
    request.state.request_id = req_id # attach the id to the request state
    token = set_request_id(req_id) # attach the id to the contextvar
    #it returns a Token object. This token represents a bookmark of the variable's previous state (which was None before this request arrived).
    #when we do reset_request_id(token), it will revert the contextvar to its previous state (None).
    
    try:
        response = await call_next(request)
        end_time = time.perf_counter()
        response_time_ms = (end_time - start_time) * 1000.0

        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time-Ms"] = f"{response_time_ms:.2f}"
        return response
    finally:
        reset_request_id(token)
