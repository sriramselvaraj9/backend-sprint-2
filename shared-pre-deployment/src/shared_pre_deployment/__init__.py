"""
shared-pre-deployment: A modular pre-deployment verification gate and orchestration runner.
"""

from __future__ import annotations

from .exceptions import (
    ConfigurationError,
    ConnectivityError,
    PreDeploymentError,
    ValidationError,
)
from .runner import Logger, PreDeploymentRunner
from .validators import (
    BaseCheck,
    CallbackCheck,
    CallbackValidator,
    CheckResult,
    CheckStatus,
    CommandCheck,
    CommandValidator,
    EnvCheck,
    EnvValidator,
    PostgresCheck,
    PostgresValidator,
    RedisCheck,
    RedisValidator,
    mask_url_password,
)

__version__ = "1.0.0"

__all__ = [
    "__version__",
    "BaseCheck",
    "CheckResult",
    "CheckStatus",
    "CallbackCheck",
    "CallbackValidator",
    "CommandCheck",
    "CommandValidator",
    "EnvCheck",
    "EnvValidator",
    "PostgresCheck",
    "PostgresValidator",
    "RedisCheck",
    "RedisValidator",
    "Logger",
    "mask_url_password",
    "PreDeploymentRunner",
    "PreDeploymentError",
    "ValidationError",
    "ConfigurationError",
    "ConnectivityError",
]
