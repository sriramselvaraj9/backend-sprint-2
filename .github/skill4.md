# Task: Film Review Platform — Pagination, Filtering & Query Optimization

Implement today's exercise in my existing Film Review Platform project. Before making changes, inspect the current codebase and understand its existing architecture, naming conventions, database models, schemas, DAOs, services, routes, and tests.

## 1. Important Rules

- Extend the existing implementation instead of rebuilding the project.
- Preserve the existing architecture: Routes → Services → DAOs → Database.
- Keep database queries inside DAO classes only.
- Keep business logic inside service classes and HTTP handling inside routes.
- Use FastAPI, Pydantic v2, SQLAlchemy 2.0 async APIs, and the existing database configuration.
- Reuse existing models, schemas, dependencies, exceptions, and response conventions wherever possible.
- Do not introduce duplicate classes, unnecessary abstractions, new dependencies, or unrelated refactoring.
- Do not break existing authentication, RBAC, Redis caching, review ownership rules, soft deletion, or API behavior.
- Do not use in-memory pagination or fetch all database records and paginate them in Python.
- Do not modify database models or create migrations unless genuinely required. Explain why before making such a change.
- Implement the changes directly in the existing project and run the relevant tests.

## 2. Offset-Based Pagination for Films

Update the existing film list endpoint to support page-number-based pagination.

Requirements:
- Accept `page` and `page_size` as query parameters.
- Use sensible defaults, such as `page=1` and `page_size=10`.
- Validate that `page >= 1` and `1 <= page_size <= 100` using FastAPI/Pydantic validation.
- Calculate the database offset as `(page - 1) * page_size`.
- Apply SQLAlchemy `.limit()` and `.offset()` in the DAO query.
- Execute a separate database count query to calculate the total number of matching films.
- Return only the records belonging to the requested page.
- Use deterministic ordering, such as `Film.id`, unless the project already defines a suitable ordering.

Return a consistent response containing:
- `page`
- `page_size`
- `total`
- `items` containing the film records for the requested page.

The `total` count must reflect the filtered records, not just the current page.

## 3. Multi-Field Film Filtering

Support these optional query parameters on the film list endpoint:

- `genre`: exact match.
- `from_year`: minimum release year, inclusive.
- `to_year`: maximum release year, inclusive.
- `director`: case-insensitive substring match.

Requirements:
- Define a Pydantic v2 schema for the filter parameters, following the existing schema conventions.
- Validate the year range when both bounds are provided. Reject `from_year > to_year` with a clear validation error.
- Accept any individual filter without requiring the others.
- Allow all filters to be combined.
- Apply only the conditions corresponding to provided values.
- Use SQLAlchemy 2.0 `select()` and dynamically construct `.where()` conditions inside the DAO.
- Apply the same filters to the count query and the data query.
- Combine filtering and pagination at the database level.
- Ensure soft-deleted or inactive films remain excluded according to the existing project rules.

For director substring matching, use a case-insensitive SQLAlchemy expression appropriate for the existing database, such as `ilike()` where supported.

## 4. Pagination and Filtering for Reviews

Apply the same offset-pagination pattern to the existing review-list endpoint for a specific film.

Requirements:
- Preserve the existing film-specific review route and authentication behavior.
- Accept `page` and `page_size` query parameters with the same validation rules.
- Return `page`, `page_size`, `total`, and `items`.
- Count only reviews belonging to the requested film.
- Apply pagination in the database using `.limit()` and `.offset()`.
- Use deterministic ordering, preferably newest reviews first with a unique tie-breaker such as review ID.
- Preserve existing review visibility, ownership, and soft-delete rules.

Do not duplicate pagination logic unnecessarily if the project already has an appropriate reusable schema or helper.

## 5. Fix N+1 Query Problems

Inspect the existing film and review listing code, service logic, schemas, ORM relationships, and response serialization.

Identify any code that triggers additional database queries for each returned record, such as:
- Loading reviews separately for each film.
- Loading film details separately for each review.
- Loading reviewer information separately for each review.

Choose the appropriate eager-loading strategy based on the relationship:
- Prefer `selectinload()` for one-to-many relationships, such as films with reviews.
- Prefer `joinedload()` for many-to-one or one-to-one relationships, such as reviews with their associated film or reviewer, when appropriate.

Important:
- The exercise requires one database round trip for the related data needed by each listing query.
- For any listing response that needs related data, prefer a single SQL query with an appropriate join or projection when feasible.
- Do not assume that `selectinload()` always produces a single SQL query; it normally uses a separate query for related collections.
- If the listing endpoint returns only scalar fields, consider a projection or explicit join instead of loading full ORM relationships.
- Account for SQLAlchemy async session behavior and prevent accidental lazy-loading during response serialization.
- If `joinedload()` is used for collection relationships, handle result deduplication with `.unique()` where required.
- Avoid loading relationships that the response does not need.
- Preserve the existing response schema and output fields.

Add or update tests to verify that listing records does not trigger a query per record. Use SQLAlchemy query instrumentation or the project's existing query-count testing approach where practical.

## 6. Cursor-Based Pagination Alternative

Implement cursor-based pagination as an alternative mode on one existing listing endpoint, preferably the film list endpoint, without removing offset-based pagination.

Requirements:
- Use a stable, unique ordering based on `Film.id` or another appropriate indexed, unique ordering field.
- Accept an optional `cursor` and a bounded `page_size`.
- Treat the cursor as an opaque string from the client's perspective.
- Encode the cursor from the last returned record's ordering value and decode it on subsequent requests.
- Validate malformed cursors and return a clear HTTP 400 response.
- Apply the cursor condition directly in the SQLAlchemy query, such as `Film.id > last_id` for ascending ID order.
- Fetch at most `page_size + 1` records to determine whether another page exists.
- Return at most `page_size` records.
- Return `next_cursor` containing the cursor for the last returned record when another page exists; otherwise return `null`.
- Return `items` and `next_cursor` in the response.
- Apply compatible film filters to cursor-based requests if they share the film listing endpoint.
- Ensure cursor pagination does not use a growing SQL OFFSET.

The cursor must be treated as an implementation detail, not as a user-facing page number.

## 7. Redis Cache Compatibility

The project already uses Redis caching. Inspect the existing film-list cache before changing the implementation.

- Include all effective filter parameters and pagination parameters in cache keys.
- Ensure different pages and different filter combinations cannot return each other's cached results.
- Include the cursor in cursor-pagination cache keys if that mode is cached.
- Preserve existing cache invalidation behavior for film creation, updates, and soft deletion.
- Do not cache incorrect total counts or mix offset-pagination and cursor-pagination response formats.
- Follow the project's existing cache design rather than introducing a second cache layer.

