# Task: Implement Async and Integration Testing for the Existing Film Review Platform

## Role

Act as a senior FastAPI developer, SQLAlchemy async specialist, pytest testing engineer, and code reviewer.

Implement the following testing exercise directly in my **existing Film Review Platform repository**. The objective is to verify that authentication, authorization, routes, services, DAOs, and database operations work together through real HTTP requests.

This is an existing project, not a new project. Inspect the repository before making changes.

## 1. Mandatory rules — follow these first

1. Inspect the complete relevant project structure before editing any files.
2. Read the existing application entry point, settings, database configuration, SQLAlchemy models, session dependencies, routers, authentication services, JWT utilities, role dependencies, services, DAOs, exception handlers, and existing tests.
3. Identify the actual dependency used by the application to provide an async database session. Use that exact dependency for test overrides.
4. Reuse the project's existing registration, login, JWT, RBAC, and CRUD implementations. Do not create duplicate implementations for testing.
5. Preserve the existing architecture, naming conventions, folder structure, API prefixes, response schemas, and error-handling conventions.
6. Preserve the rule that database access belongs in DAOs. Do not add direct database queries to routes or services if the existing architecture does not allow them.
7. Do not rewrite working application code merely to make tests easier. Make the smallest necessary changes.
8. Do not mock the authentication, service, DAO, or database layers in the main integration tests. The purpose is to test their real interaction.
9. Do not connect tests to the development or production database. Never run destructive operations against the configured application database.
10. Do not change existing production database settings to SQLite. SQLite is exclusively for the test environment.
11. Do not hardcode secrets, passwords, database credentials, user IDs, response formats, or assumed project paths. Discover the existing conventions first.
12. Do not mark tests as passed without executing them and verifying the results.
13. If a requirement conflicts with the existing implementation, explain the conflict and choose the smallest safe solution consistent with the existing architecture.
14. Do not introduce Redis, Docker, PostgreSQL services, external APIs, or other infrastructure solely for these tests.
15. Do not stop after creating test files. Run the tests, fix implementation or test issues, and report the actual result.

## 2. Phase One: Inspect and plan

Before editing, inspect:

- `pyproject.toml` and the current test dependencies.
- The FastAPI application factory or `app.main:app` entry point.
- Settings and environment configuration.
- SQLAlchemy async engine and session factory.
- The actual database session dependency used by routes.
- The SQLAlchemy declarative base and all relevant models.
- User registration and login endpoints.
- Password hashing and password verification.
- JWT creation, validation, expiration, and token response schemas.
- Role definitions and role-enforcement dependencies.
- Film CRUD routes, services, and DAOs.
- Existing Review, User, and other role-protected endpoints.
- Exception handlers and the application's standard error response format.
- Existing unit tests, fixtures, and test configuration.

Then provide a short implementation plan identifying the exact files to create or modify.

Do not proceed by assuming the example file names or function names in this prompt exist in the repository.

## 3. Phase Two: Testing dependencies and configuration

Use the project's existing package manager and dependency conventions.

Ensure the test environment includes the required compatible versions of:

- `pytest`
- `pytest-asyncio`
- `httpx`
- `aiosqlite`

Add only dependencies that are actually missing.

Configure pytest and pytest-asyncio using the existing `pyproject.toml` conventions.

Use asynchronous tests and fixtures consistently. Avoid deprecated or incompatible pytest-asyncio configuration.

The test suite must run with the project's normal test command, preferably:

`uv run pytest`

Do not modify application runtime dependencies or production settings unnecessarily.

## 4. Phase Three: Isolated SQLite test database

Create a dedicated asynchronous SQLite test database using SQLAlchemy's async engine.

Prefer an in-memory SQLite database when it is compatible with the existing models and async database setup.

Requirements:

1. Create a separate test engine using `sqlite+aiosqlite`.
2. Never reuse the application's production or development engine for test database operations.
3. Create the schema once per test session, rather than recreating every table before every test.
4. Drop the test schema and dispose of the test engine during final cleanup.
5. Ensure each test begins with predictable database state.
6. Use transaction rollback, savepoints, or another appropriate isolation strategy to reset data between tests without recreating the schema for every test.
7. Ensure that commits performed by application code do not accidentally leave data behind for subsequent tests.
8. Ensure concurrent tests cannot share mutable database state unintentionally.
9. Keep SQLite-specific setup in test code. Do not alter PostgreSQL production configuration.

Important compatibility checks:

- Import all required model modules before creating the schema so their tables are registered in the declarative metadata.
- Verify that existing SQLAlchemy column types, constraints, relationships, indexes, and foreign keys work with SQLite.
- Identify PostgreSQL-specific SQL, JSON types, enums, UUID handling, server defaults, or other unsupported features before designing fixtures.
- Do not silently change production models or migrations merely to accommodate SQLite.
- If a feature genuinely cannot be tested correctly on SQLite, document it and make the smallest justified adjustment to the test strategy.

Do not assume that a simple `yield` followed by `rollback()` guarantees isolation. Verify how the application's sessions, commits, and transactions interact with the chosen rollback strategy.

## 5. Phase Four: Override the database dependency

Identify the exact dependency function that the application uses to inject its database session.

Use `app.dependency_overrides` to replace that dependency with a test dependency that yields a session bound to the isolated SQLite test database.

Requirements:

1. The override must use the exact original dependency function object.
2. Every request in the integration tests must use the test database.
3. The real route handlers, services, DAOs, authentication logic, and authorization dependencies must continue to execute.
4. Do not override unrelated application dependencies unless absolutely necessary.
5. Restore previous dependency overrides during fixture teardown, even if a test fails.
6. Do not leave test overrides active after the test suite finishes.
7. Ensure the test session lifecycle is compatible with the rollback strategy and application-level commits.

If the application has a database dependency in more than one module, determine whether those references point to the same dependency object and override the correct object used by FastAPI.

## 6. Phase Five: Async HTTP client fixture

Create a reusable pytest fixture that provides an HTTPX `AsyncClient` configured with:

- The existing FastAPI application.
- `ASGITransport`.
- A test base URL such as `http://test`.
- The isolated SQLite database dependency override.

Use `async with` so the client is closed properly.

The fixture must have a clear setup and teardown lifecycle.

Do not start Uvicorn or a real HTTP server.

Be aware that HTTPX's `ASGITransport` does not automatically run application lifespan events in every configuration. Inspect the existing lifespan implementation. If startup or shutdown is required for the tests, manage lifespan explicitly using a compatible approach without starting a real server or connecting to production services.

## 7. Phase Six: Reusable test data and authentication helpers

Create only the reusable fixtures and helpers that are genuinely needed.

Where appropriate, provide:

- A test client fixture.
- An isolated async database session fixture.
- Valid test users for Admin, Critic, and Viewer roles.
- A valid authentication token helper that uses the application's real JWT format and validation rules.
- Film and review test-data helpers.
- A helper for registering a user and obtaining a token through the real HTTP endpoints.

Follow existing Pydantic request and response schemas.

Do not bypass authentication by injecting an artificial current user into the main integration tests.

Do not manually insert users into the database for the registration/login integration test.

For tests focused on RBAC rather than registration, creating the required role-specific users directly in the test database is acceptable if the application supports this safely and the tests still exercise the real authorization dependency.

Keep fixtures deterministic. Do not rely on execution order or data left behind by previous tests.

## 8. Phase Seven: Registration and login integration test

Implement an integration test covering the complete authentication flow.

Required sequence:

1. Submit a valid registration request through the actual registration endpoint.
2. Verify the documented success status code and response structure.
3. Verify that the registered user was persisted in the SQLite database.
4. Confirm that the stored password is hashed rather than stored in plain text.
5. Submit a login request using the newly registered user's credentials.
6. Verify the documented login status code and response structure.
7. Verify that a valid access token is returned in the expected shape defined by the actual API.
8. Use that access token in the `Authorization: Bearer <token>` header for a real protected endpoint.
9. Confirm that the authenticated request is accepted and returns the expected response.

Use the actual route paths, field names, token response schema, role defaults, and authentication conventions discovered in the repository.

Do not assume that the token response is necessarily `{"access_token": "...", "token_type": "bearer"}`. Verify the existing implementation.

Also test relevant failure cases where practical, such as invalid login credentials or missing authentication, without expanding beyond the intended scope.

## 9. Phase Eight: Film CRUD lifecycle integration tests

Exercise the existing film API through real HTTP requests and the isolated database.

### A. Admin creates a film

- Authenticate as Admin using the real authentication mechanism or a valid application-compatible test token.
- Submit a valid film creation request.
- Verify the documented success status code and response schema.
- Capture the actual returned film identifier.
- Verify that the film was persisted.

### B. Fetch the film by identifier

- Send a GET request using the returned identifier.
- Verify the success status code.
- Verify the film's actual persisted fields.

### C. Update one field

- Update a single supported field using the actual endpoint and request schema.
- Verify the documented status code and response.
- Fetch the film again.
- Confirm that the changed value persisted in the database.

### D. Viewer attempts to delete the film

- Authenticate as Viewer.
- Attempt to delete the same film.
- Verify the exact rejection status code dictated by the existing authentication and RBAC implementation.
- Verify that the film still exists and remains unchanged.

### E. Admin deletes the film

- Authenticate as Admin.
- Delete the film using the actual endpoint.
- Verify the documented success status code.
- Fetch the film list.
- Confirm that the deleted film no longer appears.

Important: Inspect whether the existing application uses hard deletion or soft deletion. If deletion is implemented as soft deletion, verify the actual expected behavior rather than assuming the database row is physically removed.

Respect existing business rules, including review restrictions and film status handling.

## 10. Phase Nine: Role-enforcement integration tests

Identify at least two additional meaningful endpoint permission pairs in the existing application.

Prefer existing endpoints that exercise different authorization rules, such as:

- Review creation or modification.
- Review ownership enforcement.
- Member or user administration.
- Another existing Admin-only operation.

Do not invent new endpoints solely to satisfy this exercise.

For each selected endpoint, test both permitted and forbidden behavior.

### Endpoint pair A

- Use a role that is allowed to perform the operation.
- Send a valid request through HTTPX.
- Verify the correct status code.
- Verify the expected response body or persisted change.
- Use a role that is not allowed to perform the operation.
- Send the same operation.
- Verify the correct rejection status code.
- Verify that the forbidden operation did not modify the database.

### Endpoint pair B

Repeat the same process for a second, distinct permission rule.

Use the actual role matrix and business rules in the repository. For example, if Critics can modify only their own reviews, verify both the owner's permitted case and another user's forbidden case when applicable.

Distinguish between authentication failure (`401`), authorization failure (`403`), and other documented rejection responses. Do not force a particular status code if the existing application's security contract specifies otherwise.

## 11. Phase Ten: Database isolation and regression checks

Add tests or fixture-level verification to demonstrate that database state does not leak between tests.

At minimum:

- Create a record in one test.
- Confirm that a subsequent independent test starts with the expected clean state.
- Verify that application-level commits do not defeat the selected rollback strategy.
- Verify that foreign-key constraints are enabled when required by the model relationships.
- Verify that the test engine is disposed of after the session finishes.
- Verify that no test requires a running PostgreSQL server or production credentials.

Keep these checks focused. Do not create a separate testing framework.

## 12. Phase Eleven: Test quality and execution

Run the relevant existing unit tests and the new integration tests.

Use the project's existing test conventions and ensure that:

- Async tests and async fixtures use the appropriate pytest-asyncio configuration.
- HTTP requests use `AsyncClient` and `ASGITransport`.
- The real application routes, services, DAOs, authentication, and authorization are exercised.
- Tests use actual database reads and writes.
- Tests do not depend on test execution order.
- Test data is cleaned up reliably.
- Tests assert response contents and database state, not just status codes.
- Assertions use the existing API response contract.
- Failures are investigated rather than hidden.
- Existing working unit tests remain passing.

Run:

`uv run pytest`

If the repository has separate test directories or markers, run the relevant targeted tests first and then the full suite.

Do not weaken assertions, skip failing tests, mock away the intended integration, or change application behavior just to obtain a passing result.

If any tests fail, identify the root cause and fix it with the smallest appropriate change.

## 13. Phase Twelve: Final report

After implementation, provide a concise report containing:

1. Files created.
2. Existing files modified.
3. How the isolated SQLite database works.
4. How the database dependency override works.
5. How session cleanup and transaction rollback are implemented.
6. The registration/login and authenticated-request coverage.
7. The film CRUD and role-enforcement coverage.
8. Exact commands used to run the tests.
9. The actual number of tests passed and failed.
10. Any remaining limitations or PostgreSQL-specific behaviors that SQLite cannot verify.

Separate verified results from anything not yet tested.

## Definition of done

The task is complete only when:

- The implementation follows the existing project architecture.
- SQLite is isolated from the development and production databases.
- The test schema is not recreated for every individual test.
- Database state is reset reliably between tests.
- All application database access in the tested request path uses the test database.
- HTTPX exercises the real FastAPI request lifecycle.
- Registration, login, token validation, and an authenticated request are tested.
- Film creation, retrieval, update, Viewer deletion rejection, and Admin deletion are tested.
- At least two additional endpoint permission pairs are tested for both permitted and forbidden behavior.
- Existing tests continue to pass.
- The full relevant test suite has been executed and its results accurately reported.

Begin with repository inspection and the implementation plan. Then implement the work incrementally, verify each stage, and finish with the test results. Do not replace the existing project with a new scaffold.