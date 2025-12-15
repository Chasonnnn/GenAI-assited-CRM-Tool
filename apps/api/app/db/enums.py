"""Enum definitions for application constants."""

from enum import Enum


class Role(str, Enum):
    """
    User roles with increasing privilege levels.
    
    - INTAKE_SPECIALIST: Intake pipeline (Stage A statuses)
    - CASE_MANAGER: Post-approval workflow (Stage B statuses)  
    - MANAGER: Business admin (org settings, invites, role overrides)
    - DEVELOPER: Platform admin (integrations, feature flags, logs)
    """
    INTAKE_SPECIALIST = "intake_specialist"
    CASE_MANAGER = "case_manager"
    MANAGER = "manager"
    DEVELOPER = "developer"
    
    @classmethod
    def has_value(cls, value: str) -> bool:
        """Check if value is a valid role."""
        return value in cls._value2member_map_


class AuthProvider(str, Enum):
    """Supported identity providers."""
    GOOGLE = "google"
    MICROSOFT = "microsoft"  # Future


class CaseStatus(str, Enum):
    """
    Case status enum covering Intake (Stage A) and Post-approval (Stage B).
    
    Stage A (Intake Pipeline):
        new_unread → contacted → followup_scheduled → application_submitted 
        → under_review → approved → pending_handoff/disqualified
    
    Stage B (Post-Approval, Case Manager only):
        pending_match → meds_started → exam_passed → embryo_transferred → delivered
    """
    # Stage A: Intake Pipeline
    NEW_UNREAD = "new_unread"
    CONTACTED = "contacted"
    FOLLOWUP_SCHEDULED = "followup_scheduled"
    APPLICATION_SUBMITTED = "application_submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    PENDING_HANDOFF = "pending_handoff"  # Awaiting case manager review
    DISQUALIFIED = "disqualified"
    
    # Stage B: Post-Approval (Case Manager only)
    PENDING_MATCH = "pending_match"
    MEDS_STARTED = "meds_started"
    EXAM_PASSED = "exam_passed"
    EMBRYO_TRANSFERRED = "embryo_transferred"
    DELIVERED = "delivered"
    
    # Archive pseudo-status (for history tracking)
    ARCHIVED = "archived"
    RESTORED = "restored"

    @classmethod
    def intake_visible(cls) -> list[str]:
        """Statuses visible to intake specialists (Stage A)."""
        return [
            cls.NEW_UNREAD.value, cls.CONTACTED.value, cls.FOLLOWUP_SCHEDULED.value,
            cls.APPLICATION_SUBMITTED.value, cls.UNDER_REVIEW.value,
            cls.APPROVED.value, cls.PENDING_HANDOFF.value, cls.DISQUALIFIED.value
        ]
    
    @classmethod
    def case_manager_only(cls) -> list[str]:
        """Statuses only accessible by case_manager+ (Stage B)."""
        return [
            cls.PENDING_MATCH.value, cls.MEDS_STARTED.value, cls.EXAM_PASSED.value,
            cls.EMBRYO_TRANSFERRED.value, cls.DELIVERED.value
        ]

    @classmethod
    def handoff_queue(cls) -> list[str]:
        """Statuses awaiting case manager review."""
        return [cls.PENDING_HANDOFF.value]


class CaseSource(str, Enum):
    """How the case was created."""
    MANUAL = "manual"
    META = "meta"
    WEBSITE = "website"
    REFERRAL = "referral"


class TaskType(str, Enum):
    """Types of tasks."""
    MEETING = "meeting"
    FOLLOW_UP = "follow_up"
    CONTACT = "contact"
    REVIEW = "review"
    OTHER = "other"


class JobType(str, Enum):
    """Types of background jobs."""
    SEND_EMAIL = "send_email"
    REMINDER = "reminder"
    WEBHOOK_RETRY = "webhook_retry"
    NOTIFICATION = "notification"


class JobStatus(str, Enum):
    """Status of background jobs."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EmailStatus(str, Enum):
    """Status of outbound emails."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class IntendedParentStatus(str, Enum):
    """
    Intended Parent status workflow.
    
    new → in_review → matched → inactive
    Plus archive/restore pseudo-statuses for history tracking.
    """
    NEW = "new"
    IN_REVIEW = "in_review"
    MATCHED = "matched"
    INACTIVE = "inactive"
    
    # Archive pseudo-statuses (for history tracking)
    ARCHIVED = "archived"
    RESTORED = "restored"


class EntityType(str, Enum):
    """Entity types for polymorphic relationships (e.g., notes)."""
    CASE = "case"
    INTENDED_PARENT = "intended_parent"


# =============================================================================
# Centralized Defaults (keep models, services, migrations in sync)
# =============================================================================

DEFAULT_CASE_STATUS = CaseStatus.NEW_UNREAD
DEFAULT_CASE_SOURCE = CaseSource.MANUAL
DEFAULT_TASK_TYPE = TaskType.OTHER
DEFAULT_JOB_STATUS = JobStatus.PENDING
DEFAULT_EMAIL_STATUS = EmailStatus.PENDING
DEFAULT_IP_STATUS = IntendedParentStatus.NEW


# =============================================================================
# Role Permission Helpers (avoid string literals, use enum values)
# =============================================================================

# Roles that can assign cases to other users
ROLES_CAN_ASSIGN = {Role.MANAGER, Role.DEVELOPER}

# Roles that can archive/restore cases
ROLES_CAN_ARCHIVE = {Role.MANAGER, Role.DEVELOPER}

# Roles that can hard-delete cases (requires is_archived=true)
ROLES_CAN_HARD_DELETE = {Role.MANAGER, Role.DEVELOPER}

# Roles that can manage org settings
ROLES_CAN_MANAGE_SETTINGS = {Role.MANAGER, Role.DEVELOPER}

# Roles that can manage integrations (Meta, webhooks, etc.)
ROLES_CAN_MANAGE_INTEGRATIONS = {Role.DEVELOPER}

# Roles that can invite new members
ROLES_CAN_INVITE = {Role.MANAGER, Role.DEVELOPER}

# Roles that can view audit logs / diagnostics
ROLES_CAN_VIEW_LOGS = {Role.DEVELOPER}
