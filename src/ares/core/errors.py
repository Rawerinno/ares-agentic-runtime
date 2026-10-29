"""Domain-level errors for the ARES runtime."""


class DomainError(ValueError):
    """Base class for invalid domain data or operations."""


class InvalidTransitionError(DomainError):
    """Raised when a task changes to a disallowed status."""
