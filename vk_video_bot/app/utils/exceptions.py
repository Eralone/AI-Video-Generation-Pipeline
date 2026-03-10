from __future__ import annotations


class UserNotFoundError(Exception):
    """Raised when a user is not found by vk_user_id."""


class UserNotAuthorizedError(Exception):
    """Raised when a user exists but is not authorized."""

