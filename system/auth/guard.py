"""Backward-compatible alias for guards."""

from system.auth.guards import get_current_user, require_auth

__all__ = ["get_current_user", "require_auth"]
