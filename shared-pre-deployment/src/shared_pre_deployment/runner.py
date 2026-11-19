"""
Pre-deployment gate orchestrator and runner.
Coordinates check execution, formats log outputs, and manages exit statuses.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Callable, Optional, Sequence

from .validators import (
    BaseCheck,
    CheckResult,
    CheckStatus,
    CallbackCheck,
    CommandCheck,
    EnvCheck,
    PostgresCheck,
    RedisCheck,
)


class Logger:
    """Standard console logger formatting pre-deployment gate output."""

    @staticmethod
    def header(title: str) -> None:
        border = "=" * max(65, len(title) + 4)
        print(f"\n{border}")
        print(f"   {title}")
        print(f"{border}\n")

    @staticmethod
    def info(msg: str) -> None:
        print(f"[PRE-DEPLOYMENT] {msg}")

    @staticmethod
    def pass_(msg: str) -> None:
        print(f"[PASS] {msg}")

    @staticmethod
    def fail(msg: str) -> None:
        print(f"[FAIL] {msg}", file=sys.stderr)

    @staticmethod
    def warn(msg: str) -> None:
        print(f"[WARN] {msg}")

    @staticmethod
    def summary_success(msg: str = "All pre-deployment safety gates passed successfully!") -> None:
        border = "=" * 65
        print(f"\n{border}")
        print(f"[PASS] {msg}")
        print(f"{border}\n")

    @staticmethod
    def summary_failure(failed_count: int, total_count: int) -> None:
        border = "=" * 65
        print(f"\n{border}", file=sys.stderr)
        print(f"[FAIL] Pre-deployment verification failed: {failed_count}/{total_count} check(s) failed.", file=sys.stderr)
        print(f"{border}\n", file=sys.stderr)


class PreDeploymentRunner:
    """
    Orchestrates the execution of pre-deployment gate checks.
    Provides clear logging, execution metrics, fail-fast capabilities, and exit codes.
    """

    def __init__(
        self,
        title: str = "Pre-Deployment Safety Gate Validation",
        fail_fast: bool = True,
        logger: Optional[Logger] = None,
    ) -> None:
        self.title = title
        self.fail_fast = fail_fast
        self.logger = logger or Logger()
        self.checks: list[BaseCheck] = []
        self.results: list[CheckResult] = []

    def add_check(self, check: BaseCheck) -> PreDeploymentRunner:
        """Register a validation check instance."""
        self.checks.append(check)
        return self

    def register_env_check(
        self,
        required_vars: Sequence[str],
        name: Optional[str] = None,
    ) -> PreDeploymentRunner:
        """Convenience method to register an environment variable check."""
        return self.add_check(EnvCheck(required_vars=required_vars, name=name))

    def register_postgres_check(
        self,
        db_url: Optional[str] = None,
        env_var: str = "DATABASE_URL",
        timeout_seconds: float = 5.0,
        name: Optional[str] = None,
    ) -> PreDeploymentRunner:
        """Convenience method to register a PostgreSQL connectivity check."""
        return self.add_check(
            PostgresCheck(
                db_url=db_url,
                env_var=env_var,
                timeout_seconds=timeout_seconds,
                name=name,
            )
        )

    def register_redis_check(
        self,
        redis_url: Optional[str] = None,
        env_var: str = "REDIS_URL",
        timeout_seconds: float = 5.0,
        name: Optional[str] = None,
    ) -> PreDeploymentRunner:
        """Convenience method to register a Redis connectivity check."""
        return self.add_check(
            RedisCheck(
                redis_url=redis_url,
                env_var=env_var,
                timeout_seconds=timeout_seconds,
                name=name,
            )
        )

    def register_command_check(
        self,
        command: str | Sequence[str],
        name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        cwd: Optional[str] = None,
    ) -> PreDeploymentRunner:
        """Convenience method to register an arbitrary command execution check."""
        return self.add_check(
            CommandCheck(
                command=command,
                name=name,
                timeout_seconds=timeout_seconds,
                cwd=cwd,
            )
        )

    def register_callback_check(
        self,
        func: Callable[[], any],
        name: str = "Custom Validation",
        timeout_seconds: Optional[float] = None,
    ) -> PreDeploymentRunner:
        """Convenience method to register a custom callable check."""
        return self.add_check(
            CallbackCheck(
                func=func,
                name=name,
                timeout_seconds=timeout_seconds,
            )
        )

    async def run(self) -> bool:
        """
        Execute all registered checks in sequence.
        Returns True if all checks passed, False otherwise.
        """
        self.results.clear()
        self.logger.header(self.title)

        all_passed = True

        for index, check in enumerate(self.checks, 1):
            self.logger.info(f"Running check {index}/{len(self.checks)}: {check.name}...")
            result = await check.run()
            self.results.append(result)

            if result.passed:
                self.logger.pass_(f"{result.message} ({result.execution_time}s)")
            else:
                self.logger.fail(f"{result.message} ({result.execution_time}s)")
                all_passed = False
                if self.fail_fast:
                    self.logger.warn("Fail-fast enabled: aborting remaining checks.")
                    break

        failed_count = sum(1 for r in self.results if not r.passed)
        if all_passed:
            self.logger.summary_success()
            return True
        else:
            self.logger.summary_failure(failed_count=failed_count, total_count=len(self.checks))
            return False

    def run_sync(self) -> int:
        """
        Synchronous execution entrypoint.
        Returns 0 on success, 1 on failure.
        """
        success = asyncio.run(self.run())
        return 0 if success else 1
