# Film Review Platform - Day 2: Pydantic v2 Schemas

A FastAPI film review platform implementing **Pydantic v2** strict validation schemas, computed fields, model-level validation, and response data filtering.

---

## Architecture

This project maintains the clean layered architecture inherited from Day 1:
```
Route → Handler → Service → DAO
```

- **Routes (`app/routes`)**: Define endpoint URLs, HTTP methods, path/query parameters, schemas, and `response_model` annotations.
- **Handlers (`app/handlers`)**: Handle request/response coordination, payload logging, and `model_dump()` / `model_dump_json()` serialization.
- **Services (`app/services`)**: Business logic layer that interfaces with DAOs.
- **DAOs (`app/daos`)**: Data access layer returning mock/placeholder objects.
- **Schemas (`app/schemas`)**: Reusable Pydantic v2 request and response models with strict typing and validators.

---

## Day 2 Pydantic v2 Features

1. **`BaseSchema` with `ConfigDict(strict=True, str_strip_whitespace=True)`**:
   - Disallows implicit type conversions (e.g., `"2020"` will not coerce to `2020` for an integer field).
   - Automatically trims leading and trailing whitespace from string inputs.
2. **`FilmCreate` & `FilmResponse`**:
   - `FilmCreate` requires `title`, `release_year`, `genre`, and `director` with `Field(...)` constraints and `@field_validator`.
   - `FilmResponse` features a `@computed_field` property (`years_ago`), computed automatically from `release_year`.
3. **`ReviewCreate` & `ReviewResponse`**:
   - `ReviewCreate` enforces `film_id: int` (strict), `rating: int` (1 to 10), and `body: str` (minimum 50 characters) using `Field(...)`.
   - `ReviewResponse` returns `id`, `film_id`, `rating`, `body`, `reviewer_display_name`, and `submitted_at: datetime`.
4. **`UserResponse` (Sensitive Data Masking)**:
   - Exposes only `username`, `email`, and `role`.
   - Strictly hides `password` from responses even when present in the internal data layer.
5. **Model-Level Validation (`@model_validator(mode="after")`)**:
   - `FilmYearRange` validates cross-field constraints: `start_year < end_year`.
6. **Serialization (`model_dump` & `model_dump_json`)**:
   - Handlers demonstrate clean serialization of validated payloads into dictionaries and JSON strings.

---

## Project Structure

```
day2/
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common.py
│   │   ├── film.py
│   │   ├── review.py
│   │   └── user.py
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
├── pyproject.toml
└── README.md
```

---

## Running Day 2

### Locally with `uv`:

```bash
uv run uvicorn app.main:app --reload
```

### With Docker:

```bash
# Build the Docker image
docker build -t film-review-platform:latest .

# Run the container
docker run -d -p 8000:8000 --name film-review-platform film-review-platform:latest
```

### With Docker Compose:

```bash
# Start container in detached mode
docker compose up --build -d

# View logs
docker compose logs -f

# Stop container
docker compose down
```

---

## API Documentation

Interactive OpenAPI documentation is available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Health check: `http://127.0.0.1:8000/health`

