# Exercise: Middleware, Background Tasks & CORS — Film Review Platform

Act as a senior backend engineer. Implement today's exercise in my existing Film Review Platform and companion Next.js frontend. Follow the existing architecture, naming conventions, and folder structure.

## 1. Inspect Before Modifying

- Inspect the existing middleware, logging, settings, database sessions, Film and Review models, DAOs, services, routes, and frontend API client.
- Understand the existing review creation flow and Film aggregate fields.
- Identify the minimum files that need changes.
- Reuse existing functions and infrastructure wherever possible.
- Preserve existing authentication, RBAC, Redis caching, schemas, exception handling, and working features.

## 2. Request ID and Logging Middleware

Implement middleware that generates a unique ID for every incoming request and returns it in the `X-Request-ID` response header.

Use appropriate, descriptive names such as:

- `request_id_middleware()` — manages the request ID lifecycle.
- `get_request_id()` — retrieves the request ID from the current request context, if a helper is necessary.
- `set_request_id()` and `reset_request_id()` — manage logging context only if separate helpers improve the existing design.

These are naming examples, not instructions to create every function. Avoid unnecessary wrappers and duplicate functionality.

Requirements:
- Generate IDs using `uuid.uuid4()`.
- Store the ID in `request.state.request_id`.
- Make the ID available to downstream services, DAOs, and log statements through a safe request-scoped logging context, such as `contextvars`, where appropriate.
- Ensure all log entries produced during a request contain the same request ID.
- Reset the context safely after each request, including when exceptions occur.
- Preserve existing structured logging and error handling.

## 3. Response-Time Middleware

Measure total request-processing duration and return it in the `X-Response-Time-Ms` response header.

Use descriptive names such as:
- `response_time_middleware()` if implemented separately.
- `elapsed_ms` for the calculated duration.
- `start_time` for the initial monotonic timestamp.

Use `time.perf_counter()` for accurate elapsed-time measurement.

Ensure both custom headers remain available on successful responses and handled application errors. Combine middleware responsibilities if that is cleaner and consistent with the existing project.

Do not create multiple middleware functions that duplicate responsibilities unnecessarily.

## 4. CORS Configuration

Configure FastAPI's `CORSMiddleware` to allow only:

`http://localhost:3000`

Requirements:
- Never use wildcard origins.
- Allow only the HTTP methods used by the frontend.
- Allow only necessary request headers, including `Content-Type` and `Authorization` if the existing authentication flow requires them.
- Enable credentials only when required by the existing authentication mechanism.
- Preserve custom response headers and existing middleware behavior.
- Expose `X-Request-ID` and `X-Response-Time-Ms` to browser JavaScript if the frontend needs to read them.

Use the existing application setup and configuration conventions.

## 5. Next.js Review Submission Page

Add a simple review submission page using the existing frontend architecture.

The page must include:
- A film selector populated from the existing API.
- A rating input matching the backend's validation rules.
- A review body field matching the backend's validation rules.
- A submit button, loading state, error messages, and success feedback.

Use descriptive function names such as:
- `fetchFilms()` — retrieves available films if no equivalent API function exists.
- `handleReviewSubmit()` — handles form submission.
- `validateReviewForm()` — validates input only if client-side validation is needed.
- `createReview()` — calls the existing review API client if no equivalent function exists.

Requirements:
- Submit to `POST /films/{film_id}/reviews`.
- Follow existing schemas, authentication, and API client conventions.
- Avoid duplicate submissions.
- Display backend validation and authorization errors.
- Use appropriate TypeScript types.
- Do not duplicate existing API functions or create a separate frontend architecture.

## 6. Background Aggregate Recalculation

After a review has been successfully committed, schedule a background task to recalculate the Film record's denormalized review count and average rating.

Use descriptive names such as:
- `recalculate_film_review_aggregates()` — coordinates aggregate recalculation.
- `get_review_aggregates_by_film_id()` — retrieves the count and average from the database, if a suitable DAO method does not already exist.
- `update_film_review_aggregates()` — updates the Film record, if a suitable DAO method does not already exist.

These names should describe each function's actual responsibility. Reuse existing functions where possible instead of creating duplicates.

Requirements:
- Use FastAPI `BackgroundTasks`.
- Register the task only after the review transaction has committed successfully.
- Return the existing review-created response without waiting for recalculation.
- Use a separate, properly managed asynchronous database session for the background task.
- Never reuse a request-scoped database session after the request ends.
- Keep database access inside DAOs and business logic inside the appropriate service layer.
- Recalculate aggregates from authoritative database records.
- Respect existing soft-delete rules and review eligibility rules.
- Handle and log background failures without falsely reporting success.
- Include the request ID in task logs when it is available.
- Preserve the existing API contract, authentication, and RBAC behavior.

Do not introduce Celery, another message broker, or unrelated infrastructure.

## 7. Function Naming Standards

Apply these rules consistently throughout all modified backend and frontend files:

- Use `snake_case` for Python functions and variables.
- Use `camelCase` for JavaScript and TypeScript functions and variables, unless the existing project convention differs.
- Use descriptive verb-based function names that explain the action performed.
- Use `get_` for retrieving values, `create_` for creation, `update_` for updates, `delete_` for deletion, and `recalculate_` for recalculation.
- Use `handle_` for event handlers and `fetch_` for data retrieval where appropriate.
- Use `is_` or `has_` for boolean-returning functions.
- Avoid vague names such as `process_data()`, `do_task()`, `helper()`, `func1()`, and `handle_data()`.
- Avoid unnecessary abbreviations and excessively long names.
- Do not rename existing public functions or change their call signatures unless required.
- Do not create a function when a suitable existing function already performs the same responsibility.
- Keep functions focused on one responsibility.
- Follow the project's existing naming conventions where they differ from these examples.

## 8. Manual Verification Only

Manually verify:
1. Successful API responses contain `X-Request-ID` and `X-Response-Time-Ms`.
2. Separate requests receive distinct request IDs.
3. Handled API errors preserve the expected headers.
4. Logs for a single request contain the same request ID.
5. The Next.js review form successfully submits a request through the browser.
6. A disallowed origin cannot access the API response through browser CORS.
7. The review-created response is not delayed by aggregate recalculation.
8. The Film review count and average rating are updated after the background task completes.

Do not claim a result was verified unless it was actually checked. Remember that CORS restrictions are enforced by browsers, not by every HTTP client.

## 9. Strict Safety Requirements

- Do not create any testing files anywhere in the project.
- Do not add files or folders inside `test/`, `tests/`, or any other testing directory.
- Do not modify or delete existing test files.
- Do not reset Git changes or overwrite existing work.
- Do not introduce unnecessary dependencies, migrations, schema changes, or configuration changes.
- Do not refactor unrelated code.
- Do not duplicate existing middleware, services, DAOs, logging utilities, database sessions, or frontend API clients.
- Keep the current folder structure unless a new module is genuinely needed.
- Add helper functions only when they improve separation of responsibilities.
- Preserve existing project functionality and conventions.

## 10. Implementation Workflow

1. Inspect the current implementation.
2. Identify the exact files that need changes and explain their responsibilities.
3. Implement the required features with clear function names.
4. Review middleware ordering, request-scoped logging, transaction boundaries, database session lifecycle, and frontend integration.
5. Inspect the Git diff to confirm that only necessary files changed.
6. Perform manual verification without creating test files.
7. Report modified files, important function names, actual verification results, and any remaining manual steps.

Implement only the requirements listed above. Prioritize correctness, maintainability, minimal changes, and preservation of the existing project architecture.