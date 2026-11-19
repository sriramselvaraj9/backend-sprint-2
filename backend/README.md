# Film Review Platform - Day 4: Async Database Layer

A FastAPI film review platform implementing an **Asynchronous PostgreSQL Database Layer** with **SQLAlchemy 2.0 (`asyncpg`)** and **Request-Scoped Session Management**, continuing from Day 3.

---

## Architecture Flow

The project preserves the clean layered architecture inherited from previous days while wiring the database layer end-to-end:

```
Client (HTTP GET /films)
   ↓
FastAPI Route (app/routes/films.py)
   ↓
Depends(get_db) (app/dependencies.py)
   ↓
AsyncSession (Scoped to HTTP request via async_sessionmaker)
   ↓
Handler (app/handlers/film_handler.py)
   ↓
Service (app/services/film_service.py)
   ↓
DAO (app/daos/film_dao.py)
   ↓
SQLAlchemy 2.0 Async Engine (create_async_engine with connection pooling)
   ↓
asyncpg driver
   ↓
PostgreSQL Database
   ↓
Film rows
   ↓
Day 2 Response Schema (FilmResponse with from_attributes=True)
   ↓
JSON Response
```

---

## Day 4 Key Implementations

### 1. SQLAlchemy 2.0 ORM Models (`app/models/`)
All models use the modern SQLAlchemy 2.0 DeclarativeBase with typed `Mapped` and `mapped_column`:
- **`Film` (`app/models/film.py`)**:
  - `id`: Integer primary key (autoincrement)
  - `title`: String(255), not null, indexed
  - `release_year`: Integer, not null, indexed
  - `genre`: String(100), not null, indexed
  - `director`: String(255), not null
  - `created_at`: DateTime(timezone=True) with `server_default=func.now()`
  - `reviews`: Relationship to `Review` (`back_populates="film"`)
- **`User` (`app/models/user.py`)**:
  - `id`: Integer primary key (autoincrement)
  - `username`: String(50), unique, not null, indexed
  - `email`: String(120), unique, not null, indexed
  - `role`: String(20), default "user", not null
  - `created_at`: DateTime(timezone=True) with `server_default=func.now()`
  - `reviews`: Relationship to `Review` (`back_populates="user"`)
- **`Review` (`app/models/review.py`)**:
  - `id`: Integer primary key (autoincrement)
  - `film_id`: ForeignKey("films.id", ondelete="CASCADE"), not null, indexed
  - `user_id`: ForeignKey("users.id", ondelete="CASCADE"), not null, indexed
  - `rating`: Integer, not null
  - `body`: Text, not null
  - `created_at`: DateTime(timezone=True) with `server_default=func.now()`
  - `film`: Relationship to `Film` (`back_populates="reviews"`)
  - `user`: Relationship to `User` (`back_populates="reviews"`)

### 2. Single Round-Trip Review Query (No N+1 Queries)
Reviews for a film are queried along with the Film title and Reviewer username in a **single database round trip** using SQLAlchemy's `joinedload`:
```python
stmt = (
    select(Review)
    .options(
        joinedload(Review.film),
        joinedload(Review.user),
    )
    .where(Review.film_id == film_id)
)
result = await db.execute(stmt)
reviews = result.scalars().all()
```
This generates a single SQL query with `LEFT OUTER JOIN` across `reviews`, `films`, and `users`.

### 3. Async Database Engine & Connection Pooling (`app/database.py`)
- Configured using `create_async_engine(settings.DATABASE_URL)` with `postgresql+asyncpg://`
- Database URL is loaded from centralized `Settings` (Day 3 config), never hardcoded
- Connection pooling parameters:
  - `pool_size=5`
  - `max_overflow=10`
  - `pool_pre_ping=True` (tests connection health before checkout)

### 4. Request-Scoped Async Session Factory (`app/dependencies.py`)
- Created using `async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)`
- Request-scoped dependency:
  ```python
  async def get_db(config: Settings = Depends(get_config)) -> AsyncGenerator[AsyncSession, None]:
      async with SessionLocal() as session:
          yield session
  ```
- Automatically yields `AsyncSession` and closes it when the HTTP request finishes.
- Preserves the existing Day 3 route function signatures.

### 5. Table Creation (`app/database.py` & `app/main.py`)
- Tables are initialized using `Base.metadata.create_all` via `conn.run_sync()` in the async engine lifespan.

### 6. Response Schema Compatibility (`app/schemas/common.py`)
- `BaseSchema` has `from_attributes=True` enabled in `ConfigDict`.
- SQLAlchemy ORM model instances convert directly into Day 2 Pydantic response models (`FilmResponse`).

---

## Project Structure

```
day4/
├── .env
├── .env.example
├── pyproject.toml
├── requirements.txt
├── README.md
├── test_day4.py
└── app/
    ├── __init__.py
    ├── main.py
    ├── config.py
    ├── database.py
    ├── dependencies.py
    ├── models/
    │   ├── __init__.py
    │   ├── film.py
    │   ├── user.py
    │   └── review.py
    ├── daos/
    │   ├── film_dao.py
    │   ├── review_dao.py
    │   └── user_dao.py
    ├── handlers/
    │   ├── film_handler.py
    │   ├── review_handler.py
    │   └── auth_user_handler.py
    ├── routes/
    │   ├── films.py
    │   ├── reviews.py
    │   └── auth_users.py
    ├── schemas/
    │   ├── common.py
    │   ├── film.py
    │   ├── review.py
    │   └── user.py
    └── services/
        ├── film_service.py
        ├── review_service.py
        └── user_service.py
```

---

## Running the Project

### 1. Configure PostgreSQL
Ensure PostgreSQL is running and update `day4/.env`:
```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/film_review_db
```

### 2. Run Verification Test Suite
```bash
python test_day4.py
```

### 3. Start the FastAPI Server
```bash
uvicorn app.main:app --reload --port 8000
```
Open interactive documentation at: [http://localhost:8000/docs](http://localhost:8000/docs)
