# Film Review Platform API Skeleton

Film Review Platform API Skeleton built using FastAPI, Pydantic, and Python.

## Architecture

This project follows a simple layered architecture:
```
Route → Handler → Service → DAO
```

- **Routes (`app/routes`)**: Define endpoint URLs, HTTP methods, path parameters, schemas, and tags.
- **Handlers (`app/handlers`)**: Handle request/response operations and call services.
- **Services (`app/services`)**: Business logic layer that calls DAOs.
- **DAOs (`app/daos`)**: Data access layer returning placeholder data.
- **Schemas (`app/schemas`)**: Pydantic request and response models.

## Project Structure

```
day1/
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── schemas/
│   │   ├── __init__.py
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

## API Endpoints

### Health Check
- `GET /health` - Public health check

### Films (`/api/v1`)
- `GET /api/v1/films` - Get all films
- `GET /api/v1/films/{film_id}` - Get film by ID
- `POST /api/v1/films` - Create a new film (`FilmCreate` $\rightarrow$ `FilmResponse`)
- `PATCH /api/v1/films/{film_id}` - Update a film by ID
- `DELETE /api/v1/films/{film_id}` - Delete a film by ID

### Reviews (`/api/v1`)
- `GET /api/v1/films/{film_id}/reviews` - Get reviews for a film
- `POST /api/v1/films/{film_id}/reviews` - Create a review for a film (`ReviewCreate` $\rightarrow$ `ReviewResponse`)
- `PATCH /api/v1/reviews/{review_id}` - Update a review by ID
- `DELETE /api/v1/reviews/{review_id}` - Delete a review by ID

### Auth / Users (`/api/v1`)
- `POST /api/v1/auth/register` - User registration (`UserCreate` $\rightarrow$ `UserResponse`)
- `POST /api/v1/auth/login` - User login (`LoginRequest`)
- `GET /api/v1/users/me` - Get current user profile
- `GET /api/v1/admin/stats` - Admin statistics

## Running the Application

To run the application locally using `uv`:

```bash
uv run uvicorn app.main:app --reload
```

Interactive OpenAPI documentation is available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
