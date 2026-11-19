#!/usr/bin/env python3
"""
Film Review Platform - Pre-Deployment Gate Runner
Powered by the deployed 'shared-pre-deployment' package.
"""

import asyncio
import os
import sys
from pathlib import Path

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Load .env file if running locally outside Docker
from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

from shared_pre_deployment import (
    CallbackCheck,
    CommandCheck,
    EnvCheck,
    PostgresCheck,
    PreDeploymentRunner,
    RedisCheck,
)


def verify_secrets_manager() -> bool:
    """Verifies that database and JWT credentials can be retrieved from AWS Secrets Manager."""
    from app.core.secrets import validate_secrets

    validate_secrets()
    return True


async def main() -> None:
    runner = PreDeploymentRunner(title="Film Review Platform - Pre-Deployment Safety Gate")

    # 1. Non-sensitive environment variables check
    runner.add_check(
        EnvCheck(
            required_vars=[
                "ACCESS_TOKEN_EXPIRE_MINUTES",
                "REFRESH_TOKEN_EXPIRE_DAYS",
                "ALLOWED_CORS_ORIGINS",
                "API_VERSION",
                "REDIS_URL",
                "S3_BUCKET_NAME",
            ],
            name="Configuration & Environment Variables",
        )
    )

    # 2. AWS Secrets Manager connectivity and validation (via CallbackCheck)
    runner.add_check(
        CallbackCheck(
            func=verify_secrets_manager,
            name="AWS Secrets Manager Connectivity",
            timeout_seconds=5.0,
        )
    )

    # 3. PostgreSQL connectivity (via PostgresCheck)
    # Lazy import settings so secrets are already verified
    def get_db_url() -> str:
        from app.core.config import settings

        return settings.DATABASE_URL

    try:
        from app.core.config import settings

        db_url = settings.DATABASE_URL
        redis_url = settings.REDIS_URL
    except Exception:
        db_url = os.environ.get("DATABASE_URL")
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    runner.add_check(
        PostgresCheck(
            db_url=db_url,
            timeout_seconds=5.0,
            name="PostgreSQL Database Reachability",
        )
    )

    # 4. Redis cache connectivity (via RedisCheck)
    runner.add_check(
        RedisCheck(
            redis_url=redis_url,
            timeout_seconds=5.0,
            name="Redis Cache Reachability",
        )
    )

    # 5. Automated test suite execution (via CommandCheck)
    runner.add_check(
        CommandCheck(
            command="pytest -v --tb=short",
            name="Automated Test Suite (pytest)",
            cwd=str(BACKEND_DIR),
        )
    )

    # Run all checks sequentially (fail-fast enabled)
    success = await runner.run()
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
