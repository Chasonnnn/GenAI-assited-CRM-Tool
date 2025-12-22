"""Enum definitions for application constants."""

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


class CaseStatus(str, Enum):
    """
    Case status enum covering Intake (Stage A) and Post-approval (Stage B).
    
    Stage A (Intake Pipeline):
        new_unread → contacted → qualified → applied → followup_scheduled
        → application_submitted → under_review → approved → pending_handoff/disqualified
    
    Stage B (Post-Approval, Case Manager only):
        pending_match → meds_started → exam_passed → embryo_transferred → delivered
    """
    # Stage A: Intake Pipeline
    NEW_UNREAD = "new_unread"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"  # Intake confirmed info, applicant is qualified
    APPLIED = "applied"  # Applicant submitted full application form
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
            cls.NEW_UNREAD.value, cls.CONTACTED.value, cls.QUALIFIED.value,
            cls.APPLIED.value, cls.FOLLOWUP_SCHEDULED.value,
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
    IMPORT = "import"  # CSV bulk import


class CaseActivityType(str, Enum):
    """Types of activities logged in case history."""
    CASE_CREATED = "case_created"
    INFO_EDITED = "info_edited"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    CASE_ASSIGNED_TO_QUEUE = "case_assigned_to_queue"
    CASE_CLAIMED = "case_claimed"
    CASE_RELEASED = "case_released"
    PRIORITY_CHANGED = "priority_changed"
    ARCHIVED = "archived"
    RESTORED = "restored"
    HANDOFF_ACCEPTED = "handoff_accepted"
    HANDOFF_DENIED = "handoff_denied"
    NOTE_ADDED = "note_added"
    NOTE_DELETED = "note_deleted"
    EMAIL_SENT = "email_sent"  # Email sent to case contact
    MATCH_PROPOSED = "match_proposed"  # New match proposed
    MATCH_REVIEWING = "match_reviewing"  # Match entered review
    MATCH_ACCEPTED = "match_accepted"  # Match accepted
    MATCH_REJECTED = "match_rejected"  # Match rejected
    MATCH_CANCELLED = "match_cancelled"  # Match cancelled/withdrawn


class MatchStatus(str, Enum):
    """
    Status of a match between surrogate (Case) and intended parent.
    
    Workflow: proposed → reviewing → accepted/rejected
    A cancelled status marks withdrawn proposals.
    """
    PROPOSED = "proposed"  # Initial match proposal
    REVIEWING = "reviewing"  # Under review by coordinator
    ACCEPTED = "accepted"  # Match finalized
    REJECTED = "rejected"  # Match declined with reason
    CANCELLED = "cancelled"  # Proposal withdrawn


class NotificationType(str, Enum):
    """Types of in-app notifications."""
    CASE_ASSIGNED = "case_assigned"
    CASE_STATUS_CHANGED = "case_status_changed"
    CASE_HANDOFF_READY = "case_handoff_ready"
    CASE_HANDOFF_ACCEPTED = "case_handoff_accepted"
    CASE_HANDOFF_DENIED = "case_handoff_denied"
    TASK_ASSIGNED = "task_assigned"
    # Future: TASK_DUE_TODAY, TASK_OVERDUE (requires worker job)


# Note: is_priority is a boolean field on Case model, not an enum
# Default: False (normal), True (priority - shown with gold styling in UI)


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
    META_LEAD_FETCH = "meta_lead_fetch"
    META_CAPI_EVENT = "meta_capi_event"
    WORKFLOW_SWEEP = "workflow_sweep"
    WORKFLOW_EMAIL = "workflow_email"
    CSV_IMPORT = "csv_import"  # Background CSV imports for large files
    EXPORT_GENERATION = "export_generation"
    DATA_PURGE = "data_purge"


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


class OwnerType(str, Enum):
    """Owner type for cases - Salesforce-style single owner model."""
    USER = "user"
    QUEUE = "queue"


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
# Week 10: Integration Health + Alerts Enums
# =============================================================================

class IntegrationType(str, Enum):
    """Types of integrations tracked for health monitoring."""
    META_LEADS = "meta_leads"
    META_CAPI = "meta_capi"
    WORKER = "worker"


class IntegrationStatus(str, Enum):
    """Health status of an integration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"


class ConfigStatus(str, Enum):
    """Configuration status of an integration."""
    CONFIGURED = "configured"
    MISSING_TOKEN = "missing_token"
    EXPIRED_TOKEN = "expired_token"


class AlertType(str, Enum):
    """Types of system alerts."""
    META_FETCH_FAILED = "meta_fetch_failed"
    META_CONVERT_FAILED = "meta_convert_failed"
    META_TOKEN_EXPIRING = "meta_token_expiring"
    META_TOKEN_EXPIRED = "meta_token_expired"
    WORKER_JOB_FAILED = "worker_job_failed"
    API_ERROR = "api_error"


class AlertSeverity(str, Enum):
    """Severity levels for alerts."""
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Status of an alert."""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SNOOZED = "snoozed"


# =============================================================================
# Automation Workflows
# =============================================================================

class WorkflowTriggerType(str, Enum):
    """Events that can trigger a workflow."""
    CASE_CREATED = "case_created"
    STATUS_CHANGED = "status_changed"
    CASE_ASSIGNED = "case_assigned"
    CASE_UPDATED = "case_updated"
    TASK_DUE = "task_due"
    TASK_OVERDUE = "task_overdue"
    SCHEDULED = "scheduled"
    INACTIVITY = "inactivity"


class WorkflowActionType(str, Enum):
    """Actions a workflow can execute."""
    SEND_EMAIL = "send_email"
    CREATE_TASK = "create_task"
    ASSIGN_CASE = "assign_case"
    SEND_NOTIFICATION = "send_notification"
    UPDATE_FIELD = "update_field"
    ADD_NOTE = "add_note"


class WorkflowConditionOperator(str, Enum):
    """Operators for workflow conditions."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    IN = "in"
    NOT_IN = "not_in"


class WorkflowExecutionStatus(str, Enum):
    """Execution result status."""
    SUCCESS = "success"
    PARTIAL = "partial"  # some actions succeeded
    FAILED = "failed"
    SKIPPED = "skipped"  # conditions not met


class WorkflowEventSource(str, Enum):
    """Source that triggered a workflow event."""
    USER = "user"
    SYSTEM = "system"
    WORKFLOW = "workflow"


# =============================================================================
# Role Permission Helpers (avoid string literals, use enum values)
# =============================================================================

# Roles that can assign cases to other users
ROLES_CAN_ASSIGN = {Role.CASE_MANAGER, Role.ADMIN, Role.DEVELOPER}

# Roles that can archive/restore cases (all roles can archive their own cases)
ROLES_CAN_ARCHIVE = {Role.INTAKE_SPECIALIST, Role.CASE_MANAGER, Role.ADMIN, Role.DEVELOPER}

# Roles that can hard-delete cases (requires is_archived=true)
ROLES_CAN_HARD_DELETE = {Role.ADMIN, Role.DEVELOPER}

# Roles that can manage org settings
ROLES_CAN_MANAGE_SETTINGS = {Role.ADMIN, Role.DEVELOPER}

# Roles that can manage integrations (Meta, webhooks, etc.)
ROLES_CAN_MANAGE_INTEGRATIONS = {Role.DEVELOPER}

# Roles that can invite new members
ROLES_CAN_INVITE = {Role.ADMIN, Role.DEVELOPER}

# Roles that can view audit logs / diagnostics
ROLES_CAN_VIEW_AUDIT = {Role.ADMIN, Role.DEVELOPER}

# Roles that can view/manage ops alerts
ROLES_CAN_VIEW_ALERTS = {Role.ADMIN, Role.DEVELOPER}


# =============================================================================
# Audit Trail
# =============================================================================

class AuditEventType(str, Enum):
    """
    Security and compliance audit events.
    
    Groups:
    - AUTH_*: Authentication events
    - SETTINGS_*: Configuration changes
    - CONFIG_*: Versioned config changes
    - DATA_*: Data exports and imports
    - AI_*: AI feature usage
    - INTEGRATION_*: Third-party connections
    """
    # Authentication
    AUTH_LOGIN_SUCCESS = "auth_login_success"
    AUTH_LOGIN_FAILED = "auth_login_failed"
    AUTH_LOGOUT = "auth_logout"
    AUTH_SESSION_REVOKED = "auth_session_revoked"
    
    # Settings changes
    SETTINGS_ORG_UPDATED = "settings_org_updated"
    SETTINGS_AI_UPDATED = "settings_ai_updated"
    SETTINGS_AI_CONSENT_ACCEPTED = "settings_ai_consent_accepted"
    SETTINGS_API_KEY_ROTATED = "settings_api_key_rotated"  # AI provider key
    
    # Versioned config changes (with before/after version links)
    CONFIG_PIPELINE_UPDATED = "config_pipeline_updated"
    CONFIG_TEMPLATE_UPDATED = "config_template_updated"
    CONFIG_ROLLED_BACK = "config_rolled_back"
    
    # Data operations
    DATA_EXPORT_CASES = "data_export_cases"
    DATA_EXPORT_ANALYTICS = "data_export_analytics"
    DATA_IMPORT_STARTED = "data_import_started"
    DATA_IMPORT_COMPLETED = "data_import_completed"

    # Compliance operations
    COMPLIANCE_EXPORT_REQUESTED = "compliance_export_requested"
    COMPLIANCE_EXPORT_DOWNLOADED = "compliance_export_downloaded"
    COMPLIANCE_LEGAL_HOLD_CREATED = "compliance_legal_hold_created"
    COMPLIANCE_LEGAL_HOLD_RELEASED = "compliance_legal_hold_released"
    COMPLIANCE_RETENTION_UPDATED = "compliance_retention_updated"
    COMPLIANCE_PURGE_PREVIEWED = "compliance_purge_previewed"
    COMPLIANCE_PURGE_EXECUTED = "compliance_purge_executed"
    
    # AI actions
    AI_ACTION_APPROVED = "ai_action_approved"
    AI_ACTION_REJECTED = "ai_action_rejected"
    AI_ACTION_FAILED = "ai_action_failed"
    AI_ACTION_DENIED = "ai_action_denied"
    
    # Integrations
    INTEGRATION_CONNECTED = "integration_connected"
    INTEGRATION_DISCONNECTED = "integration_disconnected"
    INTEGRATION_TOKEN_REFRESHED = "integration_token_refreshed"
    
    # User management
    USER_INVITED = "user_invited"
    USER_ROLE_CHANGED = "user_role_changed"
    USER_DEACTIVATED = "user_deactivated"

    # Attachments
    ATTACHMENT_UPLOADED = "attachment_uploaded"
    ATTACHMENT_DOWNLOADED = "attachment_downloaded"
    ATTACHMENT_DELETED = "attachment_deleted"


# =============================================================================
# Appointments & Scheduling
# =============================================================================

class MeetingMode(str, Enum):
    """Meeting mode for appointments."""
    ZOOM = "zoom"
    PHONE = "phone"
    IN_PERSON = "in_person"


class AppointmentStatus(str, Enum):
    """
    Appointment lifecycle status.
    
    Flow: pending → confirmed → completed
              ↘ cancelled
              ↘ no_show
              ↘ expired
    """
    PENDING = "pending"      # Awaiting approval
    CONFIRMED = "confirmed"  # Approved, scheduled
    COMPLETED = "completed"  # Meeting took place
    CANCELLED = "cancelled"  # Cancelled by client or staff
    NO_SHOW = "no_show"      # Client didn't show up
    EXPIRED = "expired"      # Pending request expired before approval


class AppointmentEmailType(str, Enum):
    """Types of emails sent for appointments."""
    REQUEST_RECEIVED = "request_received"
    CONFIRMED = "confirmed"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    REMINDER = "reminder"


# Default appointment status
DEFAULT_APPOINTMENT_STATUS = AppointmentStatus.PENDING
