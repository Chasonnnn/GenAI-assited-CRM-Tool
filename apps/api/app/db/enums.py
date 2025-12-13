"""Enum definitions for application constants."""

from enum import Enum


class Role(str, Enum):
    """
    Valid user roles.
    
    Validated at API boundary via Pydantic.
    Stored as string in database for flexibility.
    """
    MANAGER = "manager"
    INTAKE = "intake"
    SPECIALIST = "specialist"


class AuthProvider(str, Enum):
    """Supported identity providers."""
    GOOGLE = "google"
    MICROSOFT = "microsoft"  # Future support
