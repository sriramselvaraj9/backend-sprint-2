import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.core.redis import redis_client
from app.exceptions.handlers import register_exception_handlers
from app.logging_config import setup_logging
from app.middlewares import request_id_middleware
from app.routes import auth_users, films, reviews, ui

# Configure application-wide structured JSON logging
setup_logging()
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Structured log on startup
    logger.info(f"Server starting up (API version: {settings.API_VERSION})")

    yield

    # Structured log on shutdown
    logger.info("Server shutting down - disposing database engine connection pool")
    await engine.dispose()
    logger.info("Server shutting down - closing Redis client connection pool")
    await redis_client.aclose()


app = FastAPI(
    title="Film Review Platform",
    version=settings.API_VERSION,
    lifespan=lifespan,
)

# Allowed CORS origin loaded directly from settings
allowed_origins = [settings.ALLOWED_CORS_ORIGINS.strip()]

# Register HTTP Middleware for Request Tracing & Structured Logging
app.middleware("http")(request_id_middleware)

# Register CORS Middleware restricting browser cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False, #We authenticate using JWT Bearer Tokens in the Authorization header, not browser cookies/sessions. Enabling credentials when not using cookies is an unnecessary security risk.
    allow_methods=["GET", "POST", "OPTIONS"], 
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Response-Time-Ms"],
)

# Register centralized exception handlers for domain exceptions
register_exception_handlers(app)


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    return {
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
    }


# Include Application Routers with /api/v1 prefix
app.include_router(films.router, prefix="/api/v1")
app.include_router(reviews.router, prefix="/api/v1")
app.include_router(auth_users.router, prefix="/api/v1")

# Include server-rendered UI Router (separate from /api/v1 JSON endpoints)
app.include_router(ui.router, prefix="/ui")

# Include top-level routes without prefix (e.g. POST /films/{film_id}/reviews, GET /me)
app.include_router(films.router, include_in_schema=False)
app.include_router(reviews.router, include_in_schema=False)
app.include_router(auth_users.router, include_in_schema=False)
