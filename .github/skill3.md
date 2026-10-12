# Assessment Prompt: Film Search — Server-Rendered UI Fragment Using FastAPI, Jinja2, and htmx

## 1. Your Role

Act as a senior Python backend engineer and full-stack developer. Implement the assessment below inside my existing Film Review Platform project.

I am learning backend development, so the code must follow clean, understandable, beginner-friendly, and production-minded practices. Use the concepts I have already learned instead of introducing unnecessary new architecture or complicated patterns.

**Important:** Do not create a new backend project or rewrite my existing application. Inspect the existing project first and extend it safely.

## 2. My Existing Project and Learning Context

My existing Film Review Platform uses:

* FastAPI for API routes.
* SQLAlchemy 2.x with asynchronous database access.
* PostgreSQL and async database sessions.
* A layered architecture: Routes → Handlers (if already used) → Services → DAOs → Database.
* Pydantic v2 for request and response validation.
* Centralized configuration through Settings and `.env`.
* Dependency injection using FastAPI `Depends`.
* Jinja2 for server-rendered HTML templates.
* JWT authentication and role-based access control.
* Redis for caching and refresh-token management.
* Alembic for database migrations.
* Docker and Docker Compose, if already configured.

I have learned the basic htmx attributes `hx-get`, `hx-post`, `hx-put`, `hx-delete`, `hx-target`, and `hx-swap`, as well as how FastAPI's `Jinja2Templates` and `TemplateResponse` return rendered HTML.

Use the existing implementation and conventions wherever possible. Some technologies listed above may not be required for this exercise; do not add unnecessary integrations.

## 3. First Inspect the Existing Project

Before changing any files:

1. Inspect the complete relevant backend folder structure.
2. Identify the existing FastAPI application entry point and router registration pattern.
3. Inspect the Film model and determine the actual field names for title, release year, genre, and active/deleted status.
4. Inspect FilmDAO and FilmService to understand existing query methods and business logic.
5. Check how asynchronous SQLAlchemy sessions are created and injected.
6. Inspect how average film ratings are calculated and how reviews relate to films.
7. Check the existing Settings, authentication dependencies, exception handling, and API version prefixes.
8. Inspect the current `pyproject.toml`, dependency management, and Docker configuration.
9. Check whether a Next.js project already exists and inspect its package manager and conventions.

Do not assume filenames, database fields, relationship names, or function signatures. Read the actual code before implementation.

Preserve the existing architecture, naming conventions, database schema, API behavior, authentication, and Redis functionality.

Do not create duplicate database models, database engines, session factories, DAOs, or configuration objects.

## 4. Assessment Requirements

### A. Create a Separate UI Router

Create a dedicated router for server-rendered HTML views, separate from the existing JSON API routers.

Use a clearly distinct prefix:

`/ui`

The full HTML page must be available at:

`GET /ui/films`

The HTML fragment endpoint must be available at:

`GET /ui/films/search`

Follow the project's existing router organization and registration conventions. If the project uses API versioning for JSON endpoints, keep the UI routes separate from that versioned API prefix.

The UI router must reuse existing database dependencies and the existing service/DAO layer.

Do not move existing API routes into the UI router or modify their response formats.

### B. Serve a Complete HTML Page

Create a Jinja2 template for the full film search page.

Suggested location, adapted to the existing project structure:

`app/templates/ui/films.html`

The page must contain:

* A page title such as "Film Search".
* A text search input.
* A results container with a stable ID, such as `film-results`.
* A helpful initial message explaining that the user can start typing to search.
* The htmx library loaded from an official CDN script in the document head.
* Simple, readable HTML and minimal CSS.

The search input must use these htmx attributes:

* `hx-get="/ui/films/search"` to send a GET request.
* `hx-trigger="input changed delay:300ms"` to search as the user types while avoiding a request for every keystroke.
* `hx-target="#film-results"` to identify the results container.
* `hx-swap="innerHTML"` to replace only the container's contents.
* `name="q"` to send the search term to the backend.

Use a valid HTML document structure, including `DOCTYPE`, `html`, `head`, and `body`.

Do not add a submit button. Search must happen automatically while typing, without a full-page reload.

Do not introduce custom JavaScript for behavior that htmx already provides.

### C. Create the HTML Fragment Template

Create a separate Jinja2 template for the matching film cards.

Suggested location:

`app/templates/ui/partials/film_results.html`

This must be an HTML fragment, not a complete HTML document. Do not include `html`, `head`, or `body` tags.

Each matching film card must display:

* Film title.
* Release year.
* Genre.
* Average rating.

Use the real fields and relationships in the existing ORM models.

Display the average rating in a readable format, such as `8.4 / 10`, when a rating exists. Handle films without reviews gracefully, for example by displaying `Not rated`.

Use Jinja2 loops and expressions clearly. Keep presentation logic in templates and database/business logic in the existing backend layers.

If no films match, return a friendly HTML message such as "No films found."

If the search input is empty, show a sensible result according to the existing DAO capabilities and reasonable UX. Prefer returning the film catalogue when the query is empty, unless the existing application has a well-established alternative.

Never expose internal database errors, SQL statements, stack traces, passwords, tokens, or other sensitive information in the HTML response.

### D. Implement the Fragment Endpoint

Implement:

`GET /ui/films/search?q=<search-term>`

The endpoint must:

1. Accept the search term as a query parameter named `q`.
2. Normalize leading and trailing whitespace.
3. Reuse the existing FilmService and FilmDAO architecture.
4. Query films whose titles match the search term.
5. Use parameterized ORM queries rather than constructing raw SQL strings.
6. Follow the existing async SQLAlchemy patterns.
7. Respect existing soft-delete or inactive-film rules.
8. Return only the rendered film-results HTML fragment.
9. Return HTML for all normal outcomes, including an empty result list.
10. Never return a JSON list or JSON response model from this endpoint.

Use the existing DAO search method if one already exists. If it does not exist, add a small, appropriately typed DAO method that follows existing conventions and supports case-insensitive title search.

Do not put SQL queries inside the router or HTML template.

If average ratings are already calculated by an existing service or DAO query, reuse that implementation. Otherwise, add an efficient query or aggregation that obtains film results and their average ratings without creating an N+1 query problem.

Prefer a single efficient query or a small, predictable number of queries. Preserve the project's existing data-access boundaries.

If the query returns no films, render the fragment template with an empty collection instead of returning a 404 or JSON error.

Use the project's existing Jinja2 configuration where available. Do not create another template environment unnecessarily.

Follow the installed FastAPI version's correct `TemplateResponse` signature.

### E. Serve the Full Page

The `GET /ui/films` route must render the complete page template.

Use `Request` and the configured `Jinja2Templates` instance, following the conventions supported by the installed FastAPI and Starlette versions.

The full page and the fragment endpoint must be distinct routes that return HTML.

The page route should not contain database queries that belong in the DAO or service layers.

The fragment route should call the appropriate service method and pass its results to the fragment template.

### F. Keep the Architecture Clean

Use the existing structure rather than inventing a new one.

The intended responsibility boundaries are:

* **UI Router:** Receives requests and returns HTML templates.
* **FilmService:** Handles existing film-related business logic and coordinates access to data.
* **FilmDAO:** Performs database queries.
* **Jinja2 Templates:** Render the full page and film cards.
* **htmx:** Sends search requests and replaces the results area.
* **PostgreSQL:** Stores film and review data.

If the project already has handlers between routers and services, preserve that pattern where appropriate.

Do not introduce a new repository framework, generic CRUD abstraction, frontend state-management library, or extra service layer for this small feature.

Do not use Redis as the primary source of film data or introduce new caching behavior unless the existing architecture explicitly requires it.

### G. Create a Separate Minimal Next.js Application

Create or extend a separate frontend project alongside the existing API.

Use the following conceptual structure, adapted to the existing repository:

film-review-platform/

* backend/

  * app/

    * main.py
    * routers/
    * services/
    * daos/
    * models/
    * schemas/
    * templates/

      * ui/

        * films.html
        * partials/

          * film_results.html
  * pyproject.toml
  * .env.example
* frontend/

  * app/

    * page.tsx
  * package.json
  * next.config.ts (only if required)
* docker-compose.yml (preserve or extend if it already exists)

This is an illustrative structure, not permission to move existing files. If the current repository uses a different layout, preserve it and place the new frontend beside the existing backend.

The Next.js application must have one simple page that embeds the server-rendered view in an iframe.

The iframe must point to the backend UI page, using a configurable public URL or a documented environment variable, such as:

`NEXT_PUBLIC_FILM_UI_URL=http://localhost:8000/ui/films`

Use an environment variable rather than hardcoding the URL throughout the component.

The page should include a simple title, a brief description, and a responsive iframe with an accessible `title` attribute.

Do not rebuild the film search UI in React. The search input, requests, and result rendering must remain inside the FastAPI/Jinja2/htmx application.

Do not add unnecessary Next.js dependencies or create additional pages.

Provide the frontend `.env.example` and the exact commands needed to install and run the frontend.

Keep the backend and frontend independently runnable for this assessment.

### H. Prepare for Future Integration

This is Day 1 of a larger exercise. The Next.js companion frontend will be used for later work involving CORS, review submission, and Docker Compose.

For this assessment:

* Keep the iframe URL configurable.
* Do not implement review submission yet.
* Do not introduce broad CORS permissions unnecessarily.
* Do not change the existing API authentication model.
* Do not disable security headers or existing middleware to make the iframe work.
* Do not use permissive wildcard settings as a shortcut.
* Do not implement Docker Compose changes unless needed for the current repository's existing setup.
* Do not attempt to complete Day 4 or Day 8 requirements prematurely.

If the existing backend has middleware or headers that prevent iframe embedding, identify the issue and make only the smallest safe change required for the intended local development setup. Explain any browser restrictions that require configuration.

## 5. Dependencies and Configuration

Inspect the installed dependencies before changing them.

Add Jinja2 only if it is missing.

Load htmx from the CDN in the HTML document head; do not install it as a Python package.

Use the project's existing Python package manager and lockfile. Do not replace `uv` with pip or introduce another package manager without a reason.

Keep secrets out of source code. Do not overwrite `.env`, expose secret keys, or print existing secret values.

If configuration changes are necessary, update `.env.example` rather than adding real credentials.

Do not add a new database URL, engine, or session factory if one already exists.

## 6. Error Handling and Correctness

Implement the feature carefully:

* Keep existing routes and API contracts unchanged.
* Use the project's existing exception-handling conventions.
* Do not return JSON from the two UI routes during normal success or empty-result handling.
* Use correct HTTP status codes for genuine errors.
* Do not catch every exception and silently return an empty film list.
* Do not leak internal errors to users.
* Avoid duplicate queries for each film's reviews.
* Ensure all returned film fields are compatible with the template.
* Ensure imports and template paths work from the actual project root and expected startup command.
* Ensure the application continues to start correctly using its existing configuration.
* Do not modify database schemas or migrations unless a genuine schema change is necessary. This assessment should normally require no migration.

## 7. Testing Requirements

Use the existing testing framework and conventions.

Add focused tests where the existing test setup supports them.

Verify:

1. `GET /ui/films` returns HTTP 200 and a complete HTML document.
2. The full page contains the search input, htmx attributes, results container, and iframe integration remains separate.
3. `GET /ui/films/search?q=interstellar` returns an HTML fragment containing the matching film.
4. Search is case-insensitive if supported by the database's existing query conventions.
5. A query with no matches returns HTML containing the friendly empty-state message.
6. A blank or whitespace-only query follows the chosen empty-query behavior.
7. Film title, release year, genre, and average rating are rendered correctly.
8. Films without reviews display the expected fallback rating.
9. Soft-deleted or inactive films are excluded when required by existing business rules.
10. Existing JSON API routes still return their original JSON responses.
11. The new UI routes are registered and do not conflict with existing API paths.
12. The frontend page correctly uses the configurable iframe URL.

Use the project's existing database testing strategy. Do not silently substitute mocks for integration tests that are supposed to verify database behavior. If a real PostgreSQL test environment is unavailable, clearly distinguish unit-test results from unexecuted integration tests.

Run the relevant tests and available formatting, linting, and type checks. Fix failures introduced by the implementation.

Do not claim a test passed unless it was actually executed.

## 8. Implementation Workflow

Work in this order:

1. Inspect the repository and report the existing relevant structure.
2. Identify the existing models, service methods, DAO methods, database dependencies, and template conventions.
3. Propose the smallest set of file additions and modifications.
4. Implement the UI router, full-page template, fragment template, and any minimal service/DAO changes.
5. Register the router without disrupting existing routes.
6. Create or extend the separate Next.js iframe page.
7. Add the minimum necessary configuration and dependencies.
8. Add focused tests.
9. Run available checks and fix implementation errors.
10. Review the final diff for unnecessary changes, duplicated logic, secrets, and architecture violations.

Do not stop after generating a plan. Complete the implementation in the existing project, verify it, and summarize what was actually done.

If a blocking issue arises, explain it clearly and continue with the remaining work that can be safely completed.

## 9. Code Quality Rules

* Use readable Python names and appropriate type hints.
* Use async functions when following the existing async database architecture.
* Use SQLAlchemy 2.x query conventions consistent with the codebase.
* Follow existing dependency injection patterns.
* Keep routers small.
* Keep SQL and database access in the DAO layer.
* Keep business rules in the service layer.
* Keep HTML presentation in Jinja2 templates.
* Use semantic HTML and accessible labels.
* Add comments only where they explain a non-obvious decision.
* Avoid unnecessary abstractions and overly complicated code.
* Do not duplicate existing helpers or infrastructure.
* Do not rewrite unrelated files.
* Do not generate placeholder implementations for functionality that already exists.
* Do not claim industrial-grade quality merely because the code compiles; explain any remaining limitations.

## 10. Final Response Required

After implementation, provide:

1. A concise summary of what was built.
2. The final relevant folder structure.
3. A list of created and modified files, with each file's responsibility.
4. A simple explanation of how the search flow works: browser → htmx → FastAPI router → service → DAO → database → Jinja2 fragment → browser.
5. The exact commands to run the backend and frontend separately.
6. The local URLs for the full UI page, HTML fragment endpoint, existing JSON API documentation, and Next.js companion page, based on the actual project configuration.
7. Any required environment variables, without revealing secrets.
8. The tests and checks actually executed, their results, and anything that could not be verified.
9. Any known limitations or follow-up tasks for the next assessment day.

The implementation must be small, understandable, consistent with my existing Film Review Platform, and correct. Prioritize working code and architectural consistency over adding more files or introducing new technologies.
