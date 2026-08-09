"""Domain errors translated into a stable HTTP error shape by the API layer."""

from __future__ import annotations


class DomainError(Exception):
    """A rule violation the caller can fix. Carries a machine-readable code."""

    status_code = 400

    def __init__(self, message: str, code: str = "invalid_request") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class NotFoundError(DomainError):
    status_code = 404

    def __init__(self, message: str, code: str = "not_found") -> None:
        super().__init__(message, code)


class ConflictError(DomainError):
    status_code = 409

    def __init__(self, message: str, code: str = "conflict") -> None:
        super().__init__(message, code)


class PermissionDeniedError(DomainError):
    status_code = 403

    def __init__(self, message: str, code: str = "forbidden") -> None:
        super().__init__(message, code)


class ImmutableActivityError(DomainError):
    """Raised when append-only order activity is modified after insertion."""

    status_code = 409

    def __init__(self) -> None:
        super().__init__("Order activity is immutable.", code="activity_immutable")
