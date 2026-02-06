"""Custom exceptions for services."""


class AspectNotFoundError(Exception):
    """Raised when an aspect is not found."""
    pass


class AspectDeletionError(Exception):
    """Raised when trying to delete a default aspect."""
    pass


class UserAspectNotFoundError(Exception):
    """Raised when a user aspect is not found."""
    pass


class DuplicateAspectError(Exception):
    """Raised when user already has a specific aspect."""
    pass
