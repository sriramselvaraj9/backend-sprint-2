"""
Command-line interface for shared-pre-deployment.
Enables running pre-deployment gate checks directly from shell scripts or CI/CD pipelines.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Sequence

import click

from . import __version__
from .runner import PreDeploymentRunner
from .validators import CommandCheck, EnvCheck, PostgresCheck, RedisCheck


def _load_env_file(path: Optional[str]) -> None:
    """Manually parse a simple .env file without requiring external dotenv dependencies."""
    target_path = Path(path) if path else Path(".env")
    if not target_path.is_file():
        return

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k not in os.environ:
                    os.environ[k] = v
    except Exception as exc:
        print(f"[WARN] Failed to load .env file '{target_path}': {exc}", file=sys.stderr)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="shared-pre-deployment")
@click.option(
    "--title",
    default="Pre-Deployment Safety Gate Validation",
    show_default=True,
    help="Title banner displayed during execution.",
)
@click.option(
    "--env-file",
    type=click.Path(exists=False, dir_okay=False),
    default=None,
    help="Optional path to a .env file to load before running checks.",
)
@click.option(
    "--require-env",
    "require_env",
    multiple=True,
    help="Required environment variable(s). Can be specified multiple times or as comma-separated values.",
)
@click.option(
    "--check-postgres/--no-check-postgres",
    default=False,
    help="Enable or disable PostgreSQL connectivity verification.",
)
@click.option(
    "--postgres-url",
    default=None,
    help="PostgreSQL connection URL. Defaults to DATABASE_URL environment variable.",
)
@click.option(
    "--postgres-env-var",
    default="DATABASE_URL",
    show_default=True,
    help="Environment variable name holding the PostgreSQL connection URL.",
)
@click.option(
    "--check-redis/--no-check-redis",
    default=False,
    help="Enable or disable Redis connectivity verification.",
)
@click.option(
    "--redis-url",
    default=None,
    help="Redis connection URL. Defaults to REDIS_URL environment variable.",
)
@click.option(
    "--redis-env-var",
    default="REDIS_URL",
    show_default=True,
    help="Environment variable name holding the Redis connection URL.",
)
@click.option(
    "--command",
    "commands",
    multiple=True,
    help="Shell command(s) to execute as gate checks. Can be specified multiple times.",
)
@click.option(
    "--timeout",
    default=5.0,
    show_default=True,
    type=float,
    help="Default timeout in seconds for network/database checks.",
)
@click.option(
    "--fail-fast/--no-fail-fast",
    default=True,
    show_default=True,
    help="Stop on first failure.",
)
def main(
    title: str,
    env_file: Optional[str],
    require_env: Sequence[str],
    check_postgres: bool,
    postgres_url: Optional[str],
    postgres_env_var: str,
    check_redis: bool,
    redis_url: Optional[str],
    redis_env_var: str,
    commands: Sequence[str],
    timeout: float,
    fail_fast: bool,
) -> None:
    """
    Run pre-deployment safety gate verification checks.
    Exits with code 0 if all checks pass, or 1 if any check fails.
    """
    # Load .env file if specified or default exists
    _load_env_file(env_file)

    runner = PreDeploymentRunner(title=title, fail_fast=fail_fast)

    # 1. Environment Variable Validation
    if require_env:
        parsed_vars: list[str] = []
        for item in require_env:
            for v in item.split(","):
                clean = v.strip()
                if clean:
                    parsed_vars.append(clean)
        if parsed_vars:
            runner.add_check(EnvCheck(required_vars=parsed_vars))

    # 2. PostgreSQL Check
    if check_postgres or postgres_url:
        runner.add_check(
            PostgresCheck(
                db_url=postgres_url,
                env_var=postgres_env_var,
                timeout_seconds=timeout,
            )
        )

    # 3. Redis Check
    if check_redis or redis_url:
        runner.add_check(
            RedisCheck(
                redis_url=redis_url,
                env_var=redis_env_var,
                timeout_seconds=timeout,
            )
        )

    # 4. Command Checks
    for cmd in commands:
        runner.add_check(CommandCheck(command=cmd, timeout_seconds=timeout * 10))

    if not runner.checks:
        click.echo("[WARN] No checks were configured to run.", err=True)
        sys.exit(0)

    exit_code = runner.run_sync()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
