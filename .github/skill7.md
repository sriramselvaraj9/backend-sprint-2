Docker + Docker Compose — Full Stack
Exercise: Film Review Platform — Full-Stack Docker Compose

The API is complete and tested. It is time to containerise the full stack alongside the companion Next.js app built in Day 2 of this sprint — the result should be a single command that brings everything up and a system that works end-to-end across containers.

What you must build:

A multi-stage build file for the FastAPI application: a build stage that installs all dependencies and a runtime stage containing only what is needed to serve the application — no development tooling, no test files, no source files unrelated to runtime

A build context exclusion file that omits the virtual environment, compiled artefacts, the .env file, and test output from their respective image builds

A monorepo layout at the repository root: the companion Next.js app and the FastAPI backend exist as two separate workspaces each managing their own dependencies and build file; the Compose configuration lives at the root and references both

A Compose configuration defining four networked services — the API, PostgreSQL, Redis, and the Next.js frontend — with the API's database URL and cache URL referencing the other services by their Compose service names, not localhost

Health checks for the PostgreSQL and Redis services, and startup ordering that prevents the API container from accepting traffic until both dependencies report healthy

An API container entrypoint that runs migrations and the seed script before starting the server — if either step fails, the container must not start and must exit with a non-zero code

End-to-end verification: bring all four services up with a single command, open the Next.js app in a browser, perform a film search through the embedded htmx view, submit a review through the review form, and confirm the API persists the record to PostgreSQL and the background recalculation completes.