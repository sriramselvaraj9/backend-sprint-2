"""
Custom exceptions for shared-pre-deployment.
Provides standardized exception types for pre-deployment gate failures.
"""

from __future__ import annotations


class PreDeploymentError(Exception):
    """Base exception for all pre-deployment gate errors."""
    pass


class ValidationError(PreDeploymentError):
    """Raised or recorded when a validation check fails."""
    pass


class ConfigurationError(PreDeploymentError):
    """Raised when required environment configuration is missing or invalid."""
    pass


class ConnectivityError(PreDeploymentError):
    """Raised when an external service (PostgreSQL, Redis) is unreachable."""
    pass
