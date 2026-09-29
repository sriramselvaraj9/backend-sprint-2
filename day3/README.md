# Film Review Platform - Day 3: Dependency Injection & Configuration

A FastAPI film review platform implementing **Centralized Configuration** and **Reusable Shared Dependencies** (`Depends`) as part of Day 3 learning.

---

## Architecture

This project maintains the clean layered architecture inherited from Day 1 and Day 2:
```
Route (with Depends) → Handler → Service → DAO
```

- **Configuration (`app/config.py`)**: Typed configuration loaded once at import from `.env` using Pydantic Settings.
- **Dependencies (`app/dependencies.py`)**: Reusable dependency functions providing config, placeholder database sessions, and request trace IDs.
- **Routes (`app/routes`)**: Endpoints with injected dependencies (`Depends(get_config)`, `Depends(get_db)`, `Depends(get_trace_id)`).
- **Handlers (`app/handlers`)**: Request/response-level processing.
- **Services (`app/services`)**: Business logic layer.
- **DAOs (`app/daos`)**: Data access layer.
- **Schemas (`app/schemas`)**: Reusable Pydantic v2 schemas.

---

## Day 3 Features

1. **Centralized Configuration (`app/config.py`)**:
   - Typed `Settings` class using `pydantic-settings`.
   - Reads required environment variables from `.env`:
     - `DATABASE_URL`
     - `TOKEN_SECRET_KEY`
     - `ACCESS_TOKEN_EXPIRE_MINUTES`
     - `REFRESH_TOKEN_EXPIRE_DAYS`
     - `ALLOWED_CORS_ORIGINS`
     - `API_VERSION`
   - Single `settings` instance instantiated once at module import.
   - Missing required values fail at startup with a clear `ValidationError`.
   - No direct `os.getenv()` calls across the application.

2. **Config Dependency (`get_config`)**:
   - Injected into routes via `Depends(get_config)`.
   - Ensures route handlers do not directly import the global config instance.

3. **Placeholder Database Session Dependency (`get_db`)**:
   - Reusable dependency structured with `yield` and `finally` cleanup.
   - Yields `"placeholder-db-session"`.
   - Prepared so a real async session can replace it later without changing route signatures.
   - Demonstrates a simple dependency chain by depending on `get_config`.

4. **Request Trace Identifier Dependency (`get_trace_id`)**:
   - Reads `X-Request-ID` header using FastAPI `Header`.
   - If present, returns the client's trace ID.
   - If missing, automatically generates a new UUID v4 string.
   - Visible in Swagger UI / OpenAPI docs (`/docs`).

5. **Applied to Existing Routes**:
   - `GET /api/v1/films` and `GET /api/v1/films/{film_id}` inject all 3 dependencies:
     ```python
     config: Settings = Depends(get_config)
     db: str = Depends(get_db)
     trace_id: str = Depends(get_trace_id)
     ```

---

## Project Structure

```
day3/
├── .env
├── pyproject.toml
├── README.md
├── test_day3_dependencies.py
├── test_day2_validation.py
└── app/
    ├── __init__.py
    ├── main.py
    ├── config.py
    ├── dependencies.py
    ├── daos/
    ├── handlers/
    ├── routes/
    ├── schemas/
    └── services/
```

---

## Running the Application & Tests

### Run Tests
```bash
uv run python test_day3_dependencies.py
uv run python test_day2_validation.py
```

### Run Server
```bash
uv run uvicorn app.main:app --reload --port 8000
```
Open [http://localhost:8000/docs](http://localhost:8000/docs) to view Swagger UI.
