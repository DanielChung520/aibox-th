"""
@file        exceptions.py
@description RagicDataAgent custom exception hierarchy.
@lastUpdate  2026-04-11 12:52:25
@author      Daniel Chung
@version     1.0.0
"""


class RagicError(Exception):
    """Base exception for all Ragic operations."""

    def __init__(self, message: str, code: str = "RAGIC_ERROR") -> None:
        self.code = code
        super().__init__(message)


class RagicAuthError(RagicError):
    """API Key invalid or expired (HTTP 401)."""

    def __init__(self, message: str = "API Key invalid or expired") -> None:
        super().__init__(message, code="RAGIC_AUTH_FAILED")


class RagicForbiddenError(RagicError):
    """Insufficient permissions (HTTP 403)."""

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message, code="RAGIC_FORBIDDEN")


class RagicNotFoundError(RagicError):
    """Table or record not found (HTTP 404)."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, code="RAGIC_NOT_FOUND")


class RagicRateLimitError(RagicError):
    """Too many requests — Ragic enforces max 5 req/s (HTTP 429)."""

    def __init__(self, message: str = "Rate limit exceeded (max 5 req/s)") -> None:
        super().__init__(message, code="RAGIC_RATE_LIMITED")


class RagicTimeoutError(RagicError):
    """Request timed out (HTTP 504 or client timeout)."""

    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__(message, code="RAGIC_TIMEOUT")


class RagicConnectionError(RagicError):
    """Connection configuration not found or invalid."""

    def __init__(self, message: str = "Connection not found") -> None:
        super().__init__(message, code="RAGIC_CONNECTION_ERROR")
