"""Custom exceptions for services."""


class PluginNotFoundError(Exception):
    """Raised when a plugin is not found."""
    pass


class PluginDeletionError(Exception):
    """Raised when trying to delete a default plugin."""
    pass


class UserPluginNotFoundError(Exception):
    """Raised when a user plugin is not found."""
    pass


class DuplicatePluginError(Exception):
    """Raised when user already has a specific plugin."""
    pass
