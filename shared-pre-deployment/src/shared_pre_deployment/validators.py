"""
Validators and pre-deployment check components for shared-pre-deployment.

Consolidates all reusable verification checks:
- Environment variable validation (EnvCheck / EnvValidator)
- PostgreSQL database connectivity (PostgresCheck / PostgresValidator)
- Redis cache connectivity (RedisCheck / RedisValidator)
- Subprocess command execution (CommandCheck / CommandValidator)
- Custom callable callback (CallbackCheck / CallbackValidator)
- URL credential masking utility (mask_url_password)
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import inspect
import os
import re
import subprocess
import time
from typing import Any, Awaitable, Callable, Mapping, Optional, Sequence, Union

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
import redis.asyncio as aioredis


# ===========================================================================
# 1. Base Abstractions & Data Structures
# ===========================================================================

class CheckStatus(str, Enum):
    """Execution status for a gate check."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class CheckResult:
    """Result data structure returned by a pre-deployment check."""
    name: str
    status: CheckStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0

    @property
    def passed(self) -> bool:
        """Convenience property indicating whether check succeeded."""
        return self.status == CheckStatus.PASSED


class BaseCheck(ABC):
    """Abstract base class for all pre-deployment validation checks."""

    name: str

    def __init__(self, name: Optional[str] = None) -> None:
        if name:
            self.name = name

    @abstractmethod
    async def execute(self) -> CheckResult:
        """
        Execute check logic asynchronously.
        Must return a CheckResult without raising unhandled exceptions.
        """
        ...

    async def run(self) -> CheckResult:
        """Run the check with execution timing and guard against unhandled exceptions."""
        start_time = time.perf_counter()
        try:
            result = await self.execute()
        except Exception as exc:
            result = CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Unhandled exception during check execution: {exc}",
                details={"exception": str(exc)},
            )
        result.execution_time = round(time.perf_counter() - start_time, 4)
        return result


# ===========================================================================
# 2. Security & Credential Masking Utility
# ===========================================================================

# Regex to safely mask passwords in URLs (e.g. postgresql://user:pass@host:port/db or redis://:pass@host:port/db)
PASSWORD_REGEX = re.compile(r"://([^:]*):([^@]+)@")


def mask_url_password(url: Optional[str]) -> str:
    """
    Mask password in a database or service URL for safe logging.

    Examples:
        postgresql+asyncpg://admin:secret123@localhost:5432/mydb ->
        postgresql+asyncpg://admin:***@localhost:5432/mydb

        redis://:mypassword@cache.internal:6379/1 ->
        redis://:***@cache.internal:6379/1
    """
    if not url:
        return ""
    return PASSWORD_REGEX.sub(r"://\1:***@", url)


# ===========================================================================
# 3. Environment Variable Validator
# ===========================================================================

class EnvCheck(BaseCheck):
    """
    Validates that a designated list of environment variables are set and non-empty.
    Allows injecting a custom environment mapping for testing or alternate sources.
    """

    name = "Environment Variables Validation"

    def __init__(
        self,
        required_vars: Sequence[str],
        env: Optional[Mapping[str, str]] = None,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name)
        self.required_vars = list(required_vars)
        self.env = env

    async def execute(self) -> CheckResult:
        source_env = self.env if self.env is not None else os.environ

        missing: list[str] = []
        empty: list[str] = []

        for var in self.required_vars:
            val = source_env.get(var)
            if val is None:
                missing.append(var)
            elif not str(val).strip():
                empty.append(var)

        if missing or empty:
            err_parts = []
            if missing:
                err_parts.append(f"missing: {', '.join(missing)}")
            if empty:
                err_parts.append(f"empty: {', '.join(empty)}")
            msg = f"Environment validation failed ({'; '.join(err_parts)})."
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=msg,
                details={"missing": missing, "empty": empty},
            )

        return CheckResult(
            name=self.name,
            status=CheckStatus.PASSED,
            message=f"Environment validation: all {len(self.required_vars)} required configuration variables are present.",
            details={"checked": self.required_vars},
        )


EnvValidator = EnvCheck


# ===========================================================================
# 4. PostgreSQL Connectivity Validator
# ===========================================================================

class PostgresCheck(BaseCheck):
    """
    Validates PostgreSQL connectivity asynchronously using SQLAlchemy.
    Executes a simple 'SELECT 1' test query within a specified timeout.
    Safely sanitizes connection strings to prevent credential exposure in logs.
    """

    name = "PostgreSQL Connectivity Check"

    def __init__(
        self,
        db_url: Optional[str] = None,
        env_var: str = "DATABASE_URL",
        timeout_seconds: float = 5.0,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name)
        self.db_url = db_url
        self.env_var = env_var
        self.timeout_seconds = timeout_seconds

    def _resolve_url(self) -> tuple[Optional[str], str, str]:
        """Resolve database URL and compute safe display representations."""
        raw_url = self.db_url or os.environ.get(self.env_var)
        if not raw_url:
            return None, "unconfigured", ""

        try:
            parsed = make_url(raw_url)
            target = f"{parsed.host or 'localhost'}:{parsed.port or 5432}/{parsed.database or ''}"
            safe_url = parsed.render_as_string(hide_password=True)
        except Exception:
            safe_url = mask_url_password(raw_url)
            target = "configured database"

        return raw_url, target, safe_url

    async def execute(self) -> CheckResult:
        raw_url, target, safe_url = self._resolve_url()

        if not raw_url:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Database check failed: neither db_url nor environment variable '{self.env_var}' is set.",
                details={"env_var": self.env_var},
            )

        engine = None
        try:
            engine = create_async_engine(raw_url)
            async with asyncio.timeout(self.timeout_seconds):
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))

            return CheckResult(
                name=self.name,
                status=CheckStatus.PASSED,
                message=f"PostgreSQL connectivity verified successfully ({target}).",
                details={"target": target, "safe_url": safe_url},
            )
        except TimeoutError:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"PostgreSQL connection timed out after {self.timeout_seconds}s for target '{target}' ({safe_url}).",
                details={"target": target, "timeout": self.timeout_seconds},
            )
        except Exception as exc:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"PostgreSQL connection failed for target '{target}' ({safe_url}): {exc}",
                details={"target": target, "error": str(exc)},
            )
        finally:
            if engine is not None:
                await engine.dispose()


PostgresValidator = PostgresCheck


# ===========================================================================
# 5. Redis Connectivity Validator
# ===========================================================================

class RedisCheck(BaseCheck):
    """
    Validates Redis connectivity asynchronously using redis.asyncio.
    Executes a PING command within a specified timeout.
    Safely sanitizes connection strings to prevent credential exposure in logs.
    """

    name = "Redis Connectivity Check"

    def __init__(
        self,
        redis_url: Optional[str] = None,
        env_var: str = "REDIS_URL",
        timeout_seconds: float = 5.0,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name)
        self.redis_url = redis_url
        self.env_var = env_var
        self.timeout_seconds = timeout_seconds

    def _resolve_url(self) -> tuple[Optional[str], str]:
        """Resolve Redis URL and compute safe display target."""
        raw_url = self.redis_url or os.environ.get(self.env_var)
        if not raw_url:
            return None, "unconfigured"
        safe_url = mask_url_password(raw_url)
        return raw_url, safe_url

    async def execute(self) -> CheckResult:
        raw_url, safe_url = self._resolve_url()

        if not raw_url:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Redis check failed: neither redis_url nor environment variable '{self.env_var}' is set.",
                details={"env_var": self.env_var},
            )

        client = None
        target = "configured redis"
        try:
            client = aioredis.from_url(raw_url)
            kw = getattr(client.connection_pool, "connection_kwargs", {})
            host = kw.get("host", "localhost")
            port = kw.get("port", 6379)
            db = kw.get("db", 0)
            target = f"{host}:{port}/{db}"

            async with asyncio.timeout(self.timeout_seconds):
                ping_res = await client.ping()
                if not ping_res:
                    raise RuntimeError("Redis PING returned non-truthy response")

            return CheckResult(
                name=self.name,
                status=CheckStatus.PASSED,
                message=f"Redis connectivity verified successfully ({target}).",
                details={"target": target, "safe_url": safe_url},
            )
        except TimeoutError:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Redis connection timed out after {self.timeout_seconds}s for target '{target}'.",
                details={"target": target, "timeout": self.timeout_seconds},
            )
        except Exception as exc:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Redis connection failed for target '{target}': {exc}",
                details={"target": target, "error": str(exc)},
            )
        finally:
            if client is not None:
                await client.aclose()


RedisValidator = RedisCheck


# ===========================================================================
# 6. Command Execution Validator
# ===========================================================================

class CommandCheck(BaseCheck):
    """
    Executes a shell command or executable array.
    Validates that the command exits with code 0 within an optional timeout.
    """

    name = "Command Execution Gate"

    def __init__(
        self,
        command: Union[str, Sequence[str]],
        name: Optional[str] = None,
        cwd: Optional[str] = None,
        env: Optional[Mapping[str, str]] = None,
        timeout_seconds: Optional[float] = None,
        capture_output: bool = False,
    ) -> None:
        cmd_display = command if isinstance(command, str) else " ".join(command)
        super().__init__(name=name or f"Command ({cmd_display})")
        self.command = command
        self.cwd = cwd
        self.env = env
        self.timeout_seconds = timeout_seconds
        self.capture_output = capture_output

    async def execute(self) -> CheckResult:
        cmd_str = self.command if isinstance(self.command, str) else " ".join(self.command)
        run_env = dict(os.environ)
        if self.env:
            run_env.update(self.env)

        stdout_dest = subprocess.PIPE if self.capture_output else None
        stderr_dest = subprocess.PIPE if self.capture_output else None

        try:
            loop = asyncio.get_running_loop()

            def _run_sync() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    self.command,
                    shell=isinstance(self.command, str),
                    cwd=self.cwd,
                    env=run_env,
                    stdout=stdout_dest,
                    stderr=stderr_dest,
                    text=True,
                    timeout=self.timeout_seconds,
                )

            proc = await loop.run_in_executor(None, _run_sync)

            if proc.returncode == 0:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.PASSED,
                    message=f"Command '{cmd_str}' passed successfully.",
                    details={
                        "returncode": 0,
                        "stdout": proc.stdout if self.capture_output else None,
                        "stderr": proc.stderr if self.capture_output else None,
                    },
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.FAILED,
                    message=f"Command '{cmd_str}' failed with exit code {proc.returncode}.",
                    details={
                        "returncode": proc.returncode,
                        "stdout": proc.stdout if self.capture_output else None,
                        "stderr": proc.stderr if self.capture_output else None,
                    },
                )

        except subprocess.TimeoutExpired:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Command '{cmd_str}' timed out after {self.timeout_seconds}s.",
                details={"timeout": self.timeout_seconds},
            )
        except Exception as exc:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Command '{cmd_str}' execution failed: {exc}",
                details={"error": str(exc)},
            )


CommandValidator = CommandCheck


# ===========================================================================
# 7. Custom Callback Validator
# ===========================================================================

class CallbackCheck(BaseCheck):
    """
    Validates a condition using a custom Python callable (function or coroutine).
    If the function returns False or raises an exception, the check is considered FAILED.
    If the function returns True, a CheckResult, or None without raising, it is PASSED.
    """

    def __init__(
        self,
        func: Callable[[], Union[bool, CheckResult, None, Awaitable[Union[bool, CheckResult, None]]]],
        name: str = "Custom Validation Callback",
        timeout_seconds: Optional[float] = None,
    ) -> None:
        super().__init__(name=name)
        self.func = func
        self.timeout_seconds = timeout_seconds

    async def execute(self) -> CheckResult:
        try:
            if inspect.iscoroutinefunction(self.func):
                if self.timeout_seconds:
                    async with asyncio.timeout(self.timeout_seconds):
                        res = await self.func()
                else:
                    res = await self.func()
            else:
                loop = asyncio.get_running_loop()
                if self.timeout_seconds:
                    async with asyncio.timeout(self.timeout_seconds):
                        res = await loop.run_in_executor(None, self.func)
                else:
                    res = await loop.run_in_executor(None, self.func)

            if isinstance(res, CheckResult):
                return res

            if res is False:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.FAILED,
                    message=f"Callback '{self.name}' returned False.",
                )

            return CheckResult(
                name=self.name,
                status=CheckStatus.PASSED,
                message=f"Callback '{self.name}' completed successfully.",
            )

        except TimeoutError:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Callback '{self.name}' timed out after {self.timeout_seconds}s.",
            )
        except Exception as exc:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Callback '{self.name}' raised an error: {exc}",
                details={"error": str(exc)},
            )


CallbackValidator = CallbackCheck
