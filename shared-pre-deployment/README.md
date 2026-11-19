# shared-pre-deployment

A modular, extensible pre-deployment verification gate and orchestration runner for modern Python applications and microservices.

## Features

- **Environment Variable Validation**: Verify all required environment variables are set and non-empty.
- **PostgreSQL Connectivity Check**: Verify database reachability via `SELECT 1` with configurable timeouts and automatic credential masking in logs.
- **Redis Connectivity Check**: Verify Redis reachability via `PING` with configurable timeouts and target inspection.
- **Command / Subprocess Gate**: Run test suites (e.g. `pytest`), linters, or arbitrary validation scripts.
- **Custom Callbacks**: Inject custom synchronous or asynchronous validation functions.
- **Orchestration & CLI**: Easy-to-use Python API and command-line interface (`shared-pre-deployment` / `pre-deployment-runner`) with clear `[PASS]`/`[FAIL]` logging and strict non-zero exit codes.

## Installation

```bash
pip install shared-pre-deployment
```

## Quick Start (Python API)

```python
import asyncio
from shared_pre_deployment import PreDeploymentRunner, EnvCheck, PostgresCheck, RedisCheck, CommandCheck

async def main():
    runner = PreDeploymentRunner(title="My Service - Pre-Deployment Gate")
    runner.add_check(EnvCheck(required_vars=["DATABASE_URL", "REDIS_URL", "API_KEY"]))
    runner.add_check(PostgresCheck(timeout_seconds=5.0))
    runner.add_check(RedisCheck(timeout_seconds=5.0))
    runner.add_check(CommandCheck("pytest tests/unit", name="Unit Tests"))

    success = await runner.run()
    if not success:
        raise SystemExit(1)

if __name__ == "__main__":
    asyncio.run(main())
```

## Quick Start (CLI)

```bash
pre-deployment-runner \
    --require-env "DATABASE_URL,REDIS_URL,API_KEY" \
    --check-postgres \
    --check-redis \
    --command "pytest -v"
```

## License

MIT
