Update my existing Day 4 Film Review Platform project to complete the exercise:

"Async CRUD + DAO Pattern — Film Review Platform — DAO Layer"

IMPORTANT:
Use ONLY the concepts and technologies I have learned so far.

Do NOT introduce new advanced concepts, libraries, patterns, or abstractions that I have not learned yet.

Concepts I have learned and MUST use:
- FastAPI
- APIRouter
- Depends()
- Pydantic v2
- SQLAlchemy 2.0
- AsyncSession
- asyncpg
- SQLAlchemy ORM models
- DeclarativeBase
- Mapped
- mapped_column
- ForeignKey
- relationship
- select()
- insert()
- update()
- delete()
- AsyncSession.execute()
- result.scalars().all()
- result.scalar_one_or_none()
- await session.commit()
- await session.refresh()
- async/await
- Python type hints
- Dependency Injection
- DAO pattern
- Route → Handler → Service → DAO architecture
- Existing config.py
- Existing database.py
- Existing dependencies.py
- Existing ORM models
- Existing exception structure
- Existing Alembic setup

Do NOT add:
- Repository pattern
- Generic DAO/base DAO
- Unit of Work
- CQRS
- Advanced SQLAlchemy features
- New third-party libraries
- Redis
- caching
- background tasks
- middleware
- advanced authentication
- JWT implementation
- complicated generic typing
- new architecture patterns

==================================================
CURRENT PROJECT STRUCTURE
==================================================

The existing project currently has:

day4/
├── alembic/
├── app/
│   ├── daos/
│   ├── handlers/
│   ├── models/
│   ├── routes/
│   ├── schemas/
│   ├── services/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   └── main.py
├── .env
├── .env.example
├── .gitignore
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── main.py
└── pyproject.toml

Keep this existing structure.

==================================================
GOAL
==================================================

Move all direct database interaction into DAO classes.

The architecture must be:

Route → Handler → Service → DAO → Database

Routes must NOT call DAOs directly.

Handlers must NOT contain database queries.

Services must NOT contain SQLAlchemy queries.

Only DAO classes should contain direct database interaction.

==================================================
1. FilmDAO
==================================================

Create/update:

app/daos/film_dao.py

Create a typed async FilmDAO.

The DAO should receive an AsyncSession through dependency injection.

Do NOT create an AsyncSession inside the DAO.

Use the existing get_session() dependency.

Implement these methods:

1. get_by_id()

- Accept film_id: int
- Return Film | None
- Use select()
- Use scalar_one_or_none()
- If the film does not exist, return None.
- Do NOT raise a not-found exception inside the DAO.

Example structure:

async def get_by_id(self, film_id: int) -> Film | None:
    stmt = select(Film).where(Film.id == film_id)
    result = await self.session.execute(stmt)
    return result.scalar_one_or_none()

2. list_films()

Return all active films.

Support optional:
- genre
- minimum release year
- maximum release year

The filters must only be applied when the value is actually provided.

For example:

genre=None
min_year=None
max_year=None

If genre is provided:
    apply genre filter

If min_year is provided:
    apply minimum year filter

If max_year is provided:
    apply maximum year filter

Do not create unnecessary filtering logic.

Return:

list[Film]

Use:

result.scalars().all()

3. create()

Accept a Film ORM object.

Add it to the session.

Commit.

Refresh it.

Return the created Film.

Use:

session.add()
await session.commit()
await session.refresh()

4. update()

Update only the fields provided for an existing film.

Do not create a completely new Film object.

Use the existing ORM object and update the specified fields.

Commit and refresh the object.

Return Film.

Keep the implementation simple and use concepts already learned.

5. soft_delete()

Do NOT physically delete the Film row.

Set the existing active/inactive field to False.

Commit.

Refresh if needed.

Return the updated Film.

Make sure normal film listing only returns active films.

==================================================
2. ReviewDAO
==================================================

Create/update:

app/daos/review_dao.py

Create a typed async ReviewDAO.

Implement:

1. list_by_film()

Accept:

film_id: int

Return:

list[Review]

Get all reviews for the given film.

Order them by most recent first.

Use the existing Review model timestamp field.

Use SQLAlchemy select().

Use scalars().all().

2. average_rating()

Accept:

film_id: int

Return the average rating for the film.

Use SQLAlchemy query functionality that I have already learned.

Keep the implementation simple.

If the film has no reviews, return an appropriate absent value instead of inventing a value.

Use a clear type hint such as:

float | None

Do not introduce advanced SQLAlchemy concepts.

3. create()

Accept a Review ORM object.

Add it to the session.

Commit.

Refresh.

Return Review.

4. delete()

Accept review identifier.

Find the review.

If it does not exist, return an appropriate absent value instead of raising inside the DAO.

If it exists:

delete it using the AsyncSession
commit the transaction

Keep the method typed.

==================================================
3. UserDAO
==================================================

Create/update:

app/daos/user_dao.py

Create a typed async UserDAO.

Implement:

get_by_email()

Accept:

email: str

Return:

User | None

Use select() and scalar_one_or_none().

This method will later be used by the authentication service.

Do NOT implement authentication or JWT here.

Only implement the database lookup.

==================================================
4. DAO DEPENDENCIES
==================================================

Use the existing dependency injection setup.

Create DAO dependency functions if needed, for example:

def get_film_dao(
    session: AsyncSession = Depends(get_session),
) -> FilmDAO:
    return FilmDAO(session)

Do the same for ReviewDAO and UserDAO if required.

Important:

The DAO must NOT call get_session() itself.

The DAO must NOT create AsyncSession itself.

FastAPI dependency injection should provide the session.

==================================================
5. SERVICES
==================================================

Use the existing:

app/services/

Create thin service placeholders.

For example:

app/services/film_service.py

The service should receive the DAO and call DAO methods.

Example architecture:

Route
    ↓
Handler
    ↓
Service
    ↓
FilmDAO
    ↓
AsyncSession
    ↓
PostgreSQL

The service must NOT contain:

select()
insert()
update()
delete()
session.execute()
session.commit()

Those belong in the DAO.

For not-found handling:

DAO returns:

Film | None

The service can decide what that means.

For example:

film = await dao.get_by_id(film_id)

if film is None:
    raise FilmNotFoundError(...)

Keep this simple.

==================================================
6. HANDLERS
==================================================

Use the existing:

app/handlers/

Create/update thin handlers.

Handlers should call services.

Handlers should not call DAOs directly.

Do not put SQLAlchemy code in handlers.

Keep handlers simple.

==================================================
7. ROUTES
==================================================

Use the existing:

app/routes/

Update at least TWO route handlers so the complete call chain is:

Route → Handler → Service → DAO

Do NOT use:

Route → DAO

Do NOT put database queries inside routes.

Choose simple film endpoints such as:

GET /films/{film_id}

GET /films

The exact existing route naming should be preserved if those routes already exist.

Use Depends() for dependency injection.

==================================================
8. EXISTING MODELS
==================================================

Before writing code, inspect the existing models in:

app/models/

Use the existing field names and relationships.

Do NOT rename existing model fields.

Do NOT recreate models.

Do NOT add fields unless absolutely required by the exercise.

For soft delete, use the existing active/inactive field if it already exists.

For Review ordering, use the existing created-at/timestamp field.

For average rating, use the existing rating field.

For User email lookup, use the existing email field.

==================================================
9. EXISTING DATABASE SETUP
==================================================

Reuse the existing:

app/database.py
app/dependencies.py
app/config.py

Do not create a second database engine.

Do not create a second session factory.

Do not change the existing database configuration unless required to make this exercise work.

==================================================
10. CODE QUALITY
==================================================

Keep the code beginner-friendly.

Use explicit type hints.

Use simple method names.

Add short comments only where they help explain the code.

Do not over-engineer.

Do not add unnecessary abstractions.

Do not create generic classes.

Do not add unnecessary files.

==================================================
11. VALIDATION
==================================================

After implementation:

1. Check all imports.
2. Check type hints.
3. Make sure all DAO methods are async.
4. Make sure DAO methods use the injected AsyncSession.
5. Make sure no DAO creates its own session.
6. Make sure routes do not directly call DAOs.
7. Make sure handlers call services.
8. Make sure services call DAOs.
9. Make sure SQLAlchemy queries exist only in DAOs.
10. Make sure soft delete does not physically delete Film rows.
11. Make sure list_films() only returns active films.
12. Make sure optional filters are applied only when provided.
13. Make sure get_by_id() returns None when the film does not exist.
14. Make sure UserDAO.get_by_email() returns None when the user does not exist.
15. Make sure ReviewDAO.delete() handles a missing review without raising a database exception.
16. Run the existing tests if available.
17. Do not modify unrelated parts of the project.

==================================================
IMPORTANT LEARNING RESTRICTION
==================================================

This is a learning exercise.

Use ONLY what I have learned up to this point.

I am a beginner, so prefer straightforward SQLAlchemy 2.0 async code over clever or advanced implementations.

Do not teach or implement concepts from future lessons.

The final code should clearly demonstrate:

Route
  ↓
Handler
  ↓
Service
  ↓
DAO
  ↓
AsyncSession
  ↓
PostgreSQL

This architecture is the main learning goal of this exercise.