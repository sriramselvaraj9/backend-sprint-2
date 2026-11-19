"""
Comprehensive test suite for shared-pre-deployment.

Covers:
- PreDeploymentRunner orchestrator & fail-fast behavior
- Validator components (EnvCheck, PostgresCheck, RedisCheck, CommandCheck, CallbackCheck)
- Custom exceptions (PreDeploymentError, ValidationError, ConfigurationError, ConnectivityError)
- CLI options and exit codes
- Logging output and credential masking
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from click.testing import CliRunner
import pytest

from shared_pre_deployment import (
    __version__,
    BaseCheck,
    CallbackCheck,
    CheckResult,
    CheckStatus,
    CommandCheck,
    ConfigurationError,
    ConnectivityError,
    EnvCheck,
    Logger,
    PostgresCheck,
    PreDeploymentError,
    PreDeploymentRunner,
    RedisCheck,
    ValidationError,
    mask_url_password,
)
from shared_pre_deployment.cli import main


# ===========================================================================
# Mock Fixtures (Self-contained)
# ===========================================================================

@pytest.fixture
def mock_async_engine(mocker):
    """Provide a mocked SQLAlchemy async engine for testing PostgresCheck."""
    mock_conn = AsyncMock()
    mock_conn.execute.return_value = None

    mock_connect_ctx = AsyncMock()
    mock_connect_ctx.__aenter__.return_value = mock_conn
    mock_connect_ctx.__aexit__.return_value = None

    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_connect_ctx
    mock_engine.dispose = AsyncMock()

    mock_create = mocker.patch(
        "shared_pre_deployment.validators.create_async_engine",
        return_value=mock_engine,
    )
    return mock_create, mock_engine, mock_conn


@pytest.fixture
def mock_redis_client(mocker):
    """Provide a mocked async Redis client for testing RedisCheck."""
    mock_client = AsyncMock()
    mock_client.ping.return_value = True
    mock_client.aclose.return_value = None

    mock_pool = MagicMock()
    mock_pool.connection_kwargs = {"host": "localhost", "port": 6379, "db": 0}
    mock_client.connection_pool = mock_pool

    mock_from_url = mocker.patch(
        "shared_pre_deployment.validators.aioredis.from_url",
        return_value=mock_client,
    )
    return mock_from_url, mock_client


# ===========================================================================
# 1. Dummy Check & PreDeploymentRunner Orchestrator Tests
# ===========================================================================

class DummyCheck(BaseCheck):
    def __init__(self, name: str, should_pass: bool, execution_time: float = 0.01):
        super().__init__(name=name)
        self.should_pass = should_pass
        self.execution_time_mock = execution_time
        self.executed = False

    async def execute(self) -> CheckResult:
        self.executed = True
        return CheckResult(
            name=self.name,
            status=CheckStatus.PASSED if self.should_pass else CheckStatus.FAILED,
            message="Passed" if self.should_pass else "Failed",
        )


@pytest.mark.asyncio
async def test_runner_all_passed():
    runner = PreDeploymentRunner(title="All Passing Test")
    c1 = DummyCheck("Check 1", should_pass=True)
    c2 = DummyCheck("Check 2", should_pass=True)
    runner.add_check(c1).add_check(c2)

    success = await runner.run()

    assert success is True
    assert len(runner.results) == 2
    assert c1.executed and c2.executed
    assert all(r.passed for r in runner.results)


@pytest.mark.asyncio
async def test_runner_fail_fast_enabled():
    runner = PreDeploymentRunner(title="Fail Fast Test", fail_fast=True)
    c1 = DummyCheck("Check 1", should_pass=True)
    c2 = DummyCheck("Check 2 (Fails)", should_pass=False)
    c3 = DummyCheck("Check 3 (Should not run)", should_pass=True)
    runner.add_check(c1).add_check(c2).add_check(c3)

    success = await runner.run()

    assert success is False
    assert len(runner.results) == 2
    assert c1.executed is True
    assert c2.executed is True
    assert c3.executed is False  # Aborted before check 3


@pytest.mark.asyncio
async def test_runner_fail_fast_disabled():
    runner = PreDeploymentRunner(title="Fail Fast Disabled Test", fail_fast=False)
    c1 = DummyCheck("Check 1", should_pass=True)
    c2 = DummyCheck("Check 2 (Fails)", should_pass=False)
    c3 = DummyCheck("Check 3", should_pass=True)
    runner.add_check(c1).add_check(c2).add_check(c3)

    success = await runner.run()

    assert success is False
    assert len(runner.results) == 3
    assert c1.executed is True
    assert c2.executed is True
    assert c3.executed is True


def test_runner_run_sync_exit_codes():
    runner_pass = PreDeploymentRunner()
    runner_pass.add_check(DummyCheck("Passing", should_pass=True))
    assert runner_pass.run_sync() == 0

    runner_fail = PreDeploymentRunner()
    runner_fail.add_check(DummyCheck("Failing", should_pass=False))
    assert runner_fail.run_sync() == 1


def test_runner_convenience_registrations():
    runner = PreDeploymentRunner()
    runner.register_env_check(["VAR_1", "VAR_2"])
    runner.register_postgres_check(db_url="postgresql+asyncpg://localhost/db")
    runner.register_redis_check(redis_url="redis://localhost:6379/0")
    runner.register_command_check("echo 1")
    runner.register_callback_check(lambda: True)

    assert len(runner.checks) == 5


# ===========================================================================
# 2. EnvCheck Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_env_check_all_vars_present():
    env_mock = {"VAR_A": "value_a", "VAR_B": "123", "VAR_C": "true"}
    check = EnvCheck(required_vars=["VAR_A", "VAR_B", "VAR_C"], env=env_mock)
    result = await check.run()

    assert result.status == CheckStatus.PASSED
    assert result.passed is True
    assert "all 3 required configuration variables are present" in result.message


@pytest.mark.asyncio
async def test_env_check_missing_variables():
    env_mock = {"VAR_A": "present"}
    check = EnvCheck(required_vars=["VAR_A", "VAR_B", "VAR_C"], env=env_mock)
    result = await check.run()

    assert result.status == CheckStatus.FAILED
    assert result.passed is False
    assert "missing: VAR_B, VAR_C" in result.message
    assert result.details["missing"] == ["VAR_B", "VAR_C"]


@pytest.mark.asyncio
async def test_env_check_empty_variables():
    env_mock = {"VAR_A": "present", "VAR_B": "   ", "VAR_C": ""}
    check = EnvCheck(required_vars=["VAR_A", "VAR_B", "VAR_C"], env=env_mock)
    result = await check.run()

    assert result.status == CheckStatus.FAILED
    assert result.passed is False
    assert "empty: VAR_B, VAR_C" in result.message


# ===========================================================================
# 3. PostgresCheck Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_postgres_check_success(mock_async_engine):
    mock_create, mock_engine, mock_conn = mock_async_engine
    check = PostgresCheck(db_url="postgresql+asyncpg://usr:pwd@localhost:5432/testdb")
    result = await check.run()

    assert result.status == CheckStatus.PASSED
    assert result.passed is True
    assert "PostgreSQL connectivity verified successfully" in result.message
    mock_create.assert_called_once_with("postgresql+asyncpg://usr:pwd@localhost:5432/testdb")
    mock_engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_postgres_check_missing_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    check = PostgresCheck(db_url=None, env_var="DATABASE_URL")
    result = await check.run()

    assert result.status == CheckStatus.FAILED
    assert "neither db_url nor environment variable 'DATABASE_URL' is set" in result.message


@pytest.mark.asyncio
async def test_postgres_check_connection_failure(mock_async_engine):
    mock_create, mock_engine, _ = mock_async_engine
    mock_engine.connect.side_effect = ConnectionRefusedError("Connection refused by host")

    check = PostgresCheck(db_url="postgresql+asyncpg://usr:pwd@localhost:5432/testdb")
    result = await check.run()

    assert result.status == CheckStatus.FAILED
    assert "Connection refused by host" in result.message
    assert "pwd" not in result.message  # Verify credentials are not exposed
    mock_engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_postgres_check_timeout(mock_async_engine):
    _, mock_engine, mock_conn = mock_async_engine

    async def _hang(*args, **kwargs):
        await asyncio.sleep(1.0)

    mock_conn.execute.side_effect = _hang

    check = PostgresCheck(
        db_url="postgresql+asyncpg://usr:pwd@localhost:5432/testdb",
        timeout_seconds=0.05,
    )
    result = await check.run()

    assert result.status == CheckStatus.FAILED
    assert "timed out after 0.05s" in result.message
    mock_engine.dispose.assert_awaited_once()


# ===========================================================================
# 4. RedisCheck Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_redis_check_success(mock_redis_client):
    mock_from_url, mock_client = mock_redis_client
    check = RedisCheck(redis_url="redis://:secret@localhost:6379/0")
    result = await check.run()

    assert result.status == CheckStatus.PASSED
    assert result.passed is True
    assert "Redis connectivity verified successfully" in result.message
    mock_from_url.assert_called_once_with("redis://:secret@localhost:6379/0")
    mock_client.ping.assert_awaited_once()
    mock_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_redis_check_missing_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    check = RedisCheck(redis_url=None, env_var="REDIS_URL")
    result = await check.run()

    assert result.status == CheckStatus.FAILED
    assert "neither redis_url nor environment variable 'REDIS_URL' is set" in result.message


@pytest.mark.asyncio
async def test_redis_check_connection_failure(mock_redis_client):
    _, mock_client = mock_redis_client
    mock_client.ping.side_effect = ConnectionError("Cannot reach Redis port")

    check = RedisCheck(redis_url="redis://localhost:6379/0")
    result = await check.run()

    assert result.status == CheckStatus.FAILED
    assert "Cannot reach Redis port" in result.message
    mock_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_redis_check_timeout(mock_redis_client):
    _, mock_client = mock_redis_client

    async def _hang():
        await asyncio.sleep(1.0)
        return True

    mock_client.ping.side_effect = _hang

    check = RedisCheck(redis_url="redis://localhost:6379/0", timeout_seconds=0.05)
    result = await check.run()

    assert result.status == CheckStatus.FAILED
    assert "timed out after 0.05s" in result.message
    mock_client.aclose.assert_awaited_once()


# ===========================================================================
# 5. CommandCheck Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_command_check_success():
    check = CommandCheck(command="python -c \"print('OK')\"", capture_output=True)
    result = await check.run()

    assert result.status == CheckStatus.PASSED
    assert result.passed is True
    assert "passed successfully" in result.message
    assert result.details["returncode"] == 0


@pytest.mark.asyncio
async def test_command_check_non_zero_exit():
    check = CommandCheck(command="python -c \"import sys; sys.exit(42)\"")
    result = await check.run()

    assert result.status == CheckStatus.FAILED
    assert result.passed is False
    assert "failed with exit code 42" in result.message
    assert result.details["returncode"] == 42


@pytest.mark.asyncio
async def test_command_check_timeout():
    check = CommandCheck(
        command="python -c \"import time; time.sleep(1.0)\"",
        timeout_seconds=0.05,
    )
    result = await check.run()

    assert result.status == CheckStatus.FAILED
    assert "timed out after 0.05s" in result.message


# ===========================================================================
# 6. CallbackCheck Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_callback_check_sync_success():
    check = CallbackCheck(func=lambda: True, name="Sync True Check")
    result = await check.run()
    assert result.status == CheckStatus.PASSED


@pytest.mark.asyncio
async def test_callback_check_sync_failure():
    check = CallbackCheck(func=lambda: False, name="Sync False Check")
    result = await check.run()
    assert result.status == CheckStatus.FAILED


@pytest.mark.asyncio
async def test_callback_check_async_exception():
    async def _failing():
        raise ValueError("Invalid configuration state")

    check = CallbackCheck(func=_failing, name="Async Exception Check")
    result = await check.run()
    assert result.status == CheckStatus.FAILED
    assert "Invalid configuration state" in result.message


# ===========================================================================
# 7. CLI Interface Tests
# ===========================================================================

def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "--require-env" in result.output
    assert "--check-postgres" in result.output
    assert "--check-redis" in result.output


def test_cli_require_env_success():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--require-env", "PORT,HOST"],
        env={"PORT": "8000", "HOST": "localhost"},
    )
    assert result.exit_code == 0
    assert "[PASS]" in result.output


def test_cli_require_env_failure():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--require-env", "PORT,MISSING_VAR"],
        env={"PORT": "8000"},
    )
    assert result.exit_code == 1
    assert "[FAIL]" in result.output


def test_cli_commands():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--command", "python -c \"print('Hello')\""],
    )
    assert result.exit_code == 0
    assert "[PASS]" in result.output


def test_cli_commands_failure():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--command", "python -c \"import sys; sys.exit(3)\""],
    )
    assert result.exit_code == 1
    assert "[FAIL]" in result.output


# ===========================================================================
# 8. Logging & Masking Tests
# ===========================================================================

def test_mask_url_password_standard_postgres():
    url = "postgresql+asyncpg://admin:SuperSecret123!@db.internal:5432/production_db"
    masked = mask_url_password(url)
    assert "SuperSecret123!" not in masked
    assert "admin:***@db.internal:5432/production_db" in masked


def test_mask_url_password_redis_with_auth():
    url = "redis://:mypassword@cache.internal:6379/1"
    masked = mask_url_password(url)
    assert "mypassword" not in masked
    assert "redis://:***@cache.internal:6379/1" in masked


def test_mask_url_password_no_password():
    url = "redis://localhost:6379/0"
    masked = mask_url_password(url)
    assert masked == "redis://localhost:6379/0"


def test_mask_url_password_empty_or_none():
    assert mask_url_password("") == ""
    assert mask_url_password(None) == ""


def test_logger_methods_execute_without_error(capsys):
    logger = Logger()
    logger.header("Test Header")
    logger.info("Informational message")
    logger.pass_("Passed check")
    logger.warn("Warning notice")
    logger.summary_success("All good")

    captured = capsys.readouterr()
    assert "Test Header" in captured.out
    assert "[PRE-DEPLOYMENT] Informational message" in captured.out
    assert "[PASS] Passed check" in captured.out
    assert "[WARN] Warning notice" in captured.out
    assert "[PASS] All good" in captured.out


def test_logger_fail_and_summary_failure(capsys):
    logger = Logger()
    logger.fail("Failed check")
    logger.summary_failure(failed_count=2, total_count=5)

    captured = capsys.readouterr()
    assert "[FAIL] Failed check" in captured.err
    assert "[FAIL] Pre-deployment verification failed: 2/5 check(s) failed." in captured.err


# ===========================================================================
# 9. Custom Exceptions Tests
# ===========================================================================

def test_custom_exceptions_hierarchy():
    assert issubclass(ValidationError, PreDeploymentError)
    assert issubclass(ConfigurationError, PreDeploymentError)
    assert issubclass(ConnectivityError, PreDeploymentError)

    err = ValidationError("Check failed")
    assert str(err) == "Check failed"
    assert isinstance(err, PreDeploymentError)
