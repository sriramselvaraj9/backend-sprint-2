from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI

from app.routes import auth_users, films, reviews


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print({
        "event": "server_startup",
        "timestamp": datetime.now().isoformat()
    })
    yield
    # Shutdown logic
    print({
        "event": "server_shutdown",
        "timestamp": datetime.now().isoformat()
    })


app = FastAPI(
    title="Film Review Platform",
    lifespan=lifespan
)


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    }


# Include Application Routers with /api/v1 prefix
app.include_router(films.router, prefix="/api/v1")
app.include_router(reviews.router, prefix="/api/v1")
app.include_router(auth_users.router, prefix="/api/v1")
