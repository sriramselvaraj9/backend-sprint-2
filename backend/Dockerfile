# Stage 1: Build virtual environment with uv
FROM python:3.13-slim AS builder

# Copy uv binary from official Astral uv image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Environment configurations for uv and python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first for optimal Docker layer caching
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy application source code, Alembic migrations, test suite, and scripts
COPY app/ ./app
COPY alembic/ ./alembic
COPY alembic.ini ./
COPY seed.py ./
COPY worker.py ./
COPY scripts/ ./scripts
COPY tests/ ./tests
COPY pytest.ini ./
COPY README.md ./

# Sync project dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# Stage 2: Minimal runtime image
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app" \
    PATH="/app/.venv/bin:$PATH" \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

# Create non-root user for security best practices
RUN useradd -m -u 1000 appuser

# Copy virtualenv and application from builder stage
COPY --from=builder /app /app

# Set correct permissions and make scripts executable
RUN chmod +x /app/scripts/*.sh && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Health check dynamically reads configured PORT from environment
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request, os; port = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/health')" || exit 1

# Wire startup.sh as the container CMD so safety gates run automatically on every container start
CMD ["/app/scripts/startup.sh"]
