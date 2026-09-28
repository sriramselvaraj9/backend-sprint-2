# Skill Instructions — FastAPI Film Review Platform

## Main Goal

Build the Film Review Platform API Skeleton as part of my FastAPI learning.

The implementation MUST use only the FastAPI concepts and Python concepts I have already learned.

Do not introduce additional concepts, libraries, frameworks, patterns, or advanced architecture unless they are absolutely required by the task requirements.

The main priority is:

1. Complete every required task and endpoint.
2. Follow the required project architecture.
3. Use only concepts I have already learned.
4. Keep the implementation simple and beginner-friendly.
5. Do not over-engineer the project.

---

# Concepts I Have Learned

The project can use the following concepts that I have already learned:

## Python

- Functions
- Type hints
- `async` / `await`
- Dictionaries and lists
- Basic Python modules
- Packages
- `__init__.py`
- Imports
- `datetime`
- `contextlib`
- `asynccontextmanager`
- Basic exception concepts
- Basic project structure

## Project Management

- `uv`
- `pyproject.toml`
- `uv add`
- `uv run`

## FastAPI

- `FastAPI`
- `APIRouter`
- `include_router()`
- Route decorators such as:
  - `@router.get()`
  - `@router.post()`
  - `@router.patch()`
  - `@router.delete()`
- Path parameters
- Query parameters
- Request bodies
- Pydantic models
- Response models
- `response_model`
- OpenAPI
- Swagger UI at `/docs`
- Lifespan using `asynccontextmanager`
- Startup and shutdown logic
- Router tags
- API prefixes

## Architecture

I have learned this layered architecture:

Route → Handler → Service → DAO → Database

Responsibilities:

### Routes

Routes define:

- URL
- HTTP method
- path parameters
- request/response handling connection

Routes should NOT contain business logic.

### Handlers

Handlers deal with request/response-level operations and call services.

### Services

Services contain application/business logic.

### DAOs

DAOs are responsible for database access.

For this exercise, there is NO real database implementation yet.

DAO functions can return simple placeholder data.

---

# Important Learning Rule

DO NOT add concepts that I have not learned yet.

Do NOT introduce things such as:

- SQLAlchemy
- PostgreSQL
- Redis
- JWT implementation
- OAuth
- Dependency injection patterns that I have not learned
- Repository pattern
- Advanced generics
- Middleware
- Background tasks
- Advanced authentication systems
- Complex configuration systems
- Environment management libraries
- Docker
- Alembic
- Advanced Pydantic features
- Advanced design patterns
- External libraries that are not required

The task is an API SKELETON.

Do not implement a real database or real authentication.

Use simple placeholder implementations where the requirement does not require real functionality.

---

# Required Project

Create a FastAPI project named:

Film Review Platform

Use `uv` for project management.

Expected basic structure:

film-review-platform/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── films.py
│   │   ├── reviews.py
│   │   └── auth_users.py
│   │
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── film_handler.py
│   │   ├── review_handler.py
│   │   └── auth_user_handler.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── film_service.py
│   │   ├── review_service.py
│   │   └── auth_user_service.py
│   │
│   └── daos/
│       ├── __init__.py
│       ├── film_dao.py
│       ├── review_dao.py
│       └── user_dao.py
│
├── tests/
├── pyproject.toml
└── README.md

---

# Required Architecture

Follow this structure:

Route
  ↓
Handler
  ↓
Service
  ↓
DAO
  ↓
Database

For this exercise:

Route → Handler → Service → DAO

There is no real database yet.

The DAO can return placeholder data.

The important goal is to demonstrate the separation of responsibilities.

---

# Required Routers

Create three separate router modules.

## 1. Films Router

File:

app/routes/films.py

Use an `APIRouter`.

Tag:

"Films"

Required endpoints:

GET /films

GET /films/{film_id}

POST /films

PATCH /films/{film_id}

DELETE /films/{film_id}

---

## 2. Reviews Router

File:

app/routes/reviews.py

Use an `APIRouter`.

Tag:

"Reviews"

Required endpoints:

GET /films/{film_id}/reviews

POST /films/{film_id}/reviews

PATCH /reviews/{review_id}

DELETE /reviews/{review_id}

---

## 3. Auth / Users Router

File:

app/routes/auth_users.py

Use an `APIRouter`.

Tag:

"Auth / Users"

Required endpoints:

POST /auth/register

POST /auth/login

GET /users/me

GET /admin/stats

---

# API Versioning

All application routers must be mounted under:

/api/v1

Therefore the final URLs should be:

/api/v1/films

/api/v1/films/{film_id}

/api/v1/films/{film_id}/reviews

/api/v1/auth/register

/api/v1/auth/login

/api/v1/users/me

/api/v1/admin/stats

etc.

Use `include_router()` in `main.py`.

---

# Placeholder Responses

This is only an API skeleton.

Every endpoint must return a clearly labelled placeholder response.

Example:

{
    "message": "GET /films - placeholder"
}

For endpoints with path parameters, include the parameter in the response.

Example:

{
    "message": "GET /films/{film_id} - placeholder",
    "film_id": 10
}

Do not implement real CRUD functionality yet.

---

# Health Check

Create a public health-check endpoint in:

app/main.py

Endpoint:

GET /health

It must return:

- API status
- Current server timestamp

Example:

{
    "status": "ok",
    "timestamp": "..."
}

The health endpoint must NOT require authentication.

---

# Application Lifespan

Use the FastAPI lifespan approach that I have learned.

Use:

`asynccontextmanager`

There must be startup and shutdown logic.

On startup, print a structured log containing:

- event
- timestamp

Example:

{
    "event": "server_startup",
    "timestamp": "..."
}

On shutdown, print:

{
    "event": "server_shutdown",
    "timestamp": "..."
}

Do not use the old `@app.on_event()` approach.

---

# OpenAPI / Swagger Documentation

The API must work correctly with:

/docs

All routers must have tags so that the endpoints are grouped in Swagger UI.

Expected groups:

- Films
- Reviews
- Auth / Users
- Health

The complete API surface should be visible in `/docs`.

---

# Handler / Service / DAO Requirements

Because this exercise is specifically about application structure, do not put everything directly inside route files.

Use the layers.

Example:

films.py

→ calls film_handler.py

film_handler.py

→ calls film_service.py

film_service.py

→ calls film_dao.py

film_dao.py

→ returns placeholder data

Keep these functions simple.

Do not add unnecessary abstractions.

---

# Database Requirement

There is NO real database requirement for this exercise.

Do not install or implement:

- SQLAlchemy
- PostgreSQL
- SQLite database logic
- Alembic
- Database migrations

The DAO layer should exist only to demonstrate the architecture.

It can return placeholder data.

---

# Authentication Requirement

There is NO real authentication implementation required.

Do not implement:

- JWT
- OAuth
- Password hashing
- Login sessions
- Token generation

The auth endpoints only need to exist and return placeholder responses.

---

# Coding Style

Keep code:

- Simple
- Readable
- Beginner-friendly
- Consistent
- Easy to understand

Prefer straightforward functions.

Do not create unnecessary classes.

Do not create unnecessary helper functions.

Do not add unnecessary files.

Do not add unnecessary dependencies.

---

# Dependency Rule

Only install dependencies required for this exercise.

Expected main dependencies:

- fastapi
- uvicorn

Do not add additional packages unless the requirement absolutely needs them.

---

# Verification

After implementation, verify:

1. The project starts successfully.
2. `/health` works.
3. `/docs` opens.
4. All three routers are registered.
5. All required endpoints appear in `/docs`.
6. Tags are displayed correctly.
7. Path parameters work.
8. Startup log appears.
9. Shutdown log appears.
10. The layered structure is maintained.

Run the application using:

uv run uvicorn app.main:app --reload

---

# Final Requirement

Before considering the task complete, compare the implementation against the original requirements.

Do NOT mark the task complete if any required endpoint, router, health check, lifecycle hook, tag, or architectural layer is missing.

At the same time, do NOT add features that were not requested.

The goal is:

Complete the required Film Review Platform API Skeleton using only the FastAPI and Python concepts I have already learned.