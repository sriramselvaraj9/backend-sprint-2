# Film Review Platform — Service Layer, Centralized Exceptions & Structured Logging

Implement the following exercise in the existing **Film Review Platform** project.

## Concepts I learned today

Use and demonstrate these concepts:

1. **Service Layer**

   * Business logic belongs in the service layer.
   * Services coordinate DAOs.
   * Services must not directly access the database.
   * Route handlers must remain thin.

2. **Layered Request Flow**

   ```text
   Route → Handler → Service → DAO → Database
   ```

3. **Custom Exceptions**

   * Create domain-specific exception classes.
   * Exceptions should contain typed identifiers and descriptive messages.

4. **Centralized Exception Handling**

   * Register one centralized FastAPI exception handler.
   * Convert domain exceptions into consistent HTTP responses.
   * Do not use try/except blocks for domain errors inside route handlers.

5. **Python Logging**

   * Logger
   * Log levels
   * Handlers
   * Formatters

6. **Structured Logging**

   * Log entries must be JSON objects.
   * Every log must contain:

     * log level
     * ISO-8601 timestamp
     * logger name
     * message

7. **Request-Scoped Logging**

   * Use the existing request trace identifier from Day 3.
   * Every log produced during one request must contain the same request ID.

---

# Requirements

## 1. Create the Service Layer

Create:

```text
services/
├── film_service.py
└── review_service.py
```

### FilmService

Create a typed `FilmService` class.

It should use `FilmDAO` and `ReviewDAO` through dependency injection or constructor injection.

Implement the required business rule:

### Film soft-delete rule

A film cannot be soft-deleted if it still has active reviews.

For this exercise, define:

```text
Active review = a review that currently exists and has not been deleted.
```

Use the existing DAO functionality where possible.

Do not put database queries directly inside the service.

The service should ask the DAO for the required information and make the business decision.

Example flow:

```text
FilmService
    ↓
Check active reviews through DAO
    ↓
If active reviews exist
    → raise domain exception
    ↓
Otherwise
    → ask FilmDAO to soft-delete the film
```

---

## 2. ReviewService

Create a typed `ReviewService` class.

It should use the appropriate DAOs.

Implement these business rules:

### Rule 1 — One review per user per film

A user must not be allowed to submit more than one review for the same film.

Before creating a review:

```text
Check whether the user already reviewed the film
        ↓
If yes → raise domain exception
        ↓
If no → create review through DAO
```

Do not directly query the database from the service.

---

### Rule 2 — Only the original reviewer can update

A review's:

* rating
* body

may only be updated by the user who originally created the review.

Example:

```text
Current user ID
       ↓
Compare with review.user_id
       ↓
Same user → allow update
Different user → raise exception
```

The service should perform this business rule.

The DAO should only handle the database operation.

---

## 3. Custom Domain Exceptions

Create a dedicated module, for example:

```text
exceptions/
└── domain.py
```

Create custom exceptions for each business rule violation.

For example:

```text
ReviewAlreadyExistsError
ReviewUnauthorisedError
FilmHasActiveReviewsError
```

You may create a suitable base domain exception if useful.

Each exception must contain:

* a typed identifier for the affected resource
* a descriptive message

Example:

```python
class ReviewAlreadyExistsError(Exception):
    def __init__(self, film_id: int, user_id: int):
        self.film_id = film_id
        self.user_id = user_id
        self.message = "User has already submitted a review for this film"
        super().__init__(self.message)
```

Keep the implementation simple and typed.

---

# 4. Centralized FastAPI Exception Handler

Register centralized exception handling on the FastAPI application.

Create a suitable module such as:

```text
exceptions/
└── handlers.py
```

Register the handlers on the FastAPI application.

Do not put domain-error `try/except` blocks inside route handlers.

The centralized handler should map domain exceptions to appropriate HTTP status codes.

Use sensible mappings such as:

```text
ReviewAlreadyExistsError
→ 409 Conflict

ReviewUnauthorisedError
→ 403 Forbidden

FilmHasActiveReviewsError
→ 409 Conflict
```

The response must always follow the same structure:

```json
{
    "type": "ReviewAlreadyExistsError",
    "message": "User has already submitted a review for this film",
    "detail": {
        ...
    }
}
```

The `detail` field should contain useful structured information about the affected resource.

For example:

```json
{
    "film_id": 10,
    "user_id": 5
}
```

Keep the response format consistent for all domain exceptions.

---

# 5. Keep Route Handlers Thin

Update the existing film and review routes to use the service layer.

The route should follow this structure:

```text
Route
  ↓
Service
  ↓
DAO
```

Routes should only handle:

* HTTP request data
* dependency injection
* calling the service
* returning the response

Do not put business rules inside routes.

Do not put direct database queries inside routes.

Do not add domain-error `try/except` blocks to routes.

---

# 6. Structured JSON Logging

Configure application-wide structured logging.

Create a logging module such as:

```text
logging_config.py
```

Use Python's standard `logging` module.

Create:

* Logger
* Handler
* Formatter

Every log entry must be a JSON object containing at minimum:

```json
{
    "level": "INFO",
    "timestamp": "2026-10-05T10:30:00+00:00",
    "logger": "film_service",
    "message": "Film created"
}
```

The timestamp must be ISO-8601 format.

Use appropriate log levels:

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

Do not replace Python logging with `print()`.

---

# 7. Request Trace ID in Every Log

Day 3 already introduced a request trace identifier.

Reuse the existing implementation rather than creating an unrelated second system.

Every log generated during a request must contain the same request ID.

Example:

```json
{
    "level": "INFO",
    "timestamp": "2026-10-05T10:30:00+00:00",
    "logger": "review_service",
    "message": "Creating review",
    "request_id": "abc-123"
}
```

Another log from the same request:

```json
{
    "level": "INFO",
    "timestamp": "2026-10-05T10:30:01+00:00",
    "logger": "review_dao",
    "message": "Review created",
    "request_id": "abc-123"
}
```

The request ID must remain the same throughout the request lifecycle.

---

# 8. Logging Locations

Add useful logs at important points, for example:

### Service

```text
Creating review
Checking whether user already reviewed film
Review creation rejected
Review created successfully
```

### Exception handler

```text
Domain exception occurred
```

### Film deletion

```text
Checking active reviews
Film deletion rejected because active reviews exist
Film soft-deleted successfully
```

Do not add excessive logs for every single line of code.

---

# 9. Project Architecture

Keep the existing architecture:

```text
Routes
   ↓
Services
   ↓
DAOs
   ↓
Database
```

With exceptions and logging supporting the application:

```text
                 ┌── Exception Handler
                 │
Routes → Services → DAOs → Database
   │        │
   └────────┴── Structured Logging
```

The responsibilities must remain clear:

```text
Route
→ HTTP request/response

Service
→ Business rules and orchestration

DAO
→ Database operations

Exception Handler
→ Domain exception → HTTP response

Logger
→ Application observability
```

---

# Important Constraints

1. Use the existing project structure and existing DAOs.
2. Do not rewrite unrelated code.
3. Do not introduce new libraries unless absolutely necessary.
4. Prefer Python standard library logging.
5. Do not access the database directly from services.
6. Do not access the database from routes.
7. Do not put business rules in routes.
8. Do not use domain-error try/except blocks in routes.
9. Reuse the existing Day 3 request trace ID implementation.
10. Keep the code beginner-friendly and strongly typed.
11. Add comments explaining important parts of the implementation.
12. Do not introduce concepts that have not been covered yet unless required by the task.

---

# Implementation Order

Implement in this order:

```text
1. Custom domain exceptions
2. FilmService
3. ReviewService
4. Centralized exception handlers
5. Structured logging configuration
6. Request ID logging context
7. Update routes to use services
8. Test the complete request flow
```

After implementation, explain briefly:

* What files were created or changed
* What each file is responsible for
* How the request flows through Route → Service → DAO
* How domain exceptions reach the centralized handler
* How the request ID appears in every log
* How each business rule is enforced

Do not give a long theoretical explanation. Focus on implementing the exercise correctly using the concepts learned today.
