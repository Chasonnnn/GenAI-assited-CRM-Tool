"""Auth-related enums."""

from enum import Enum


class Role(str, Enum):
    """
    User roles with increasing privilege levels.

    - INTAKE_SPECIALIST: Intake pipeline (Stage A statuses)
    - CASE_MANAGER: Post-approval workflow (Stage B statuses)
    - ADMIN: Business admin (org settings, invites, role overrides)
    - DEVELOPER: Platform admin (integrations, feature flags, logs)
    """

    INTAKE_SPECIALIST = "intake_specialist"
    CASE_MANAGER = "case_manager"
    ADMIN = "admin"
    DEVELOPER = "developer"

    @classmethod
    def has_value(cls, value: str) -> bool:
        """Check if value is a valid role."""
        return value in cls._value2member_map_


class AuthProvider(str, Enum):
    """Supported identity providers."""

    GOOGLE = "google"
    MICROSOFT = "microsoft"  # Future
