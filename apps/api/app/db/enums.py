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


class SurrogateStatus(str, Enum):
    """
    Surrogate status enum covering Intake (Stage A) and Post-approval (Stage B).

    Stage A (Intake Pipeline):
        new_unread → contacted → qualified → interview_scheduled
        → application_submitted → under_review → approved → lost/disqualified

    Stage B (Post-Approval, Case Manager only):
        ready_to_match → matched → medical_clearance_passed → legal_clearance_passed
        → transfer_cycle → second_hcg_confirmed → heartbeat_confirmed
        → ob_care_established → anatomy_scanned → delivered
    """

    # Stage A: Intake Pipeline
    NEW_UNREAD = "new_unread"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"  # Intake confirmed info, applicant is qualified
    INTERVIEW_SCHEDULED = "interview_scheduled"  # Interview scheduled with applicant
    APPLICATION_SUBMITTED = "application_submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    LOST = "lost"
    DISQUALIFIED = "disqualified"

    # Stage B: Post-Approval (Case Manager only)
    READY_TO_MATCH = "ready_to_match"  # Ready for matching with intended parents
    MATCHED = "matched"
    MEDICAL_CLEARANCE_PASSED = "medical_clearance_passed"  # Medical exams completed
    LEGAL_CLEARANCE_PASSED = "legal_clearance_passed"  # Legal contracts finalized
    TRANSFER_CYCLE = "transfer_cycle"  # Embryo transfer cycle
    SECOND_HCG_CONFIRMED = "second_hcg_confirmed"  # Second HCG test confirmed
    HEARTBEAT_CONFIRMED = "heartbeat_confirmed"  # Fetal heartbeat confirmed
    OB_CARE_ESTABLISHED = "ob_care_established"  # OB care established
    ANATOMY_SCANNED = "anatomy_scanned"  # Anatomy scan completed
    DELIVERED = "delivered"

    # Archive pseudo-status (for history tracking)
    ARCHIVED = "archived"
    RESTORED = "restored"

    @classmethod
    def intake_visible(cls) -> list[str]:
        """Statuses visible to intake specialists (Stage A)."""
        return [
            cls.NEW_UNREAD.value,
            cls.CONTACTED.value,
            cls.QUALIFIED.value,
            cls.INTERVIEW_SCHEDULED.value,
            cls.APPLICATION_SUBMITTED.value,
            cls.UNDER_REVIEW.value,
            cls.APPROVED.value,
            cls.LOST.value,
            cls.DISQUALIFIED.value,
        ]

    @classmethod
    def surrogate_manager_only(cls) -> list[str]:
        """Statuses only accessible by case_manager+ (Stage B)."""
        return [
            cls.READY_TO_MATCH.value,
            cls.MATCHED.value,
            cls.MEDICAL_CLEARANCE_PASSED.value,
            cls.LEGAL_CLEARANCE_PASSED.value,
            cls.TRANSFER_CYCLE.value,
            cls.SECOND_HCG_CONFIRMED.value,
            cls.HEARTBEAT_CONFIRMED.value,
            cls.OB_CARE_ESTABLISHED.value,
            cls.ANATOMY_SCANNED.value,
            cls.DELIVERED.value,
        ]


class SurrogateSource(str, Enum):
    """How the surrogate record was created."""

    MANUAL = "manual"
    META = "meta"
    WEBSITE = "website"
    REFERRAL = "referral"
    IMPORT = "import"  # CSV bulk import


class SurrogateActivityType(str, Enum):
    """Types of activities logged in surrogate history."""

    SURROGATE_CREATED = "surrogate_created"
    INFO_EDITED = "info_edited"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    SURROGATE_ASSIGNED_TO_QUEUE = "surrogate_assigned_to_queue"
    SURROGATE_CLAIMED = "surrogate_claimed"
    SURROGATE_RELEASED = "surrogate_released"
    PRIORITY_CHANGED = "priority_changed"
    ARCHIVED = "archived"
    RESTORED = "restored"
    NOTE_ADDED = "note_added"
    NOTE_DELETED = "note_deleted"
    ATTACHMENT_ADDED = "attachment_added"
    ATTACHMENT_DELETED = "attachment_deleted"
    EMAIL_SENT = "email_sent"  # Email sent to surrogate contact
    TASK_CREATED = "task_created"  # Task created for surrogate
    TASK_DELETED = "task_deleted"  # Task deleted for surrogate
    MATCH_PROPOSED = "match_proposed"  # New match proposed
    MATCH_REVIEWING = "match_reviewing"  # Match entered review
    MATCH_ACCEPTED = "match_accepted"  # Match accepted
    MATCH_REJECTED = "match_rejected"  # Match rejected
    MATCH_CANCELLED = "match_cancelled"  # Match cancelled/withdrawn
    APPLICATION_EDITED = "application_edited"
    PROFILE_EDITED = "profile_edited"
    PROFILE_HIDDEN = "profile_hidden"
    CONTACT_ATTEMPT = "contact_attempt"  # Contact attempt logged
    WORKFLOW_APPROVAL_RESOLVED = (
        "workflow_approval_resolved"  # Workflow approval approved/denied/expired
    )
    WORKFLOW_APPROVAL_INVALIDATED = (
        "workflow_approval_invalidated"  # Approval invalidated (owner change)
    )
    # Medical/Insurance/Pregnancy updates (no PHI logged, just audit trail)
    MEDICAL_INFO_UPDATED = "medical_info_updated"
    INSURANCE_INFO_UPDATED = "insurance_info_updated"
    PREGNANCY_DATES_UPDATED = "pregnancy_dates_updated"
    # Journey featured images
    JOURNEY_IMAGE_SET = "journey_image_set"
    JOURNEY_IMAGE_CLEARED = "journey_image_cleared"


class MatchStatus(str, Enum):
    """
    Status of a match between surrogate and intended parent.

    Workflow: proposed → reviewing → accepted/rejected
    A cancelled status marks withdrawn proposals.
    """

    PROPOSED = "proposed"  # Initial match proposal
    REVIEWING = "reviewing"  # Under review by coordinator
    ACCEPTED = "accepted"  # Match finalized
    CANCEL_PENDING = "cancel_pending"  # Cancellation pending admin approval
    REJECTED = "rejected"  # Match declined with reason
    CANCELLED = "cancelled"  # Proposal withdrawn


class MatchEventType(str, Enum):
    """
    Types of events for Match calendar.

    Color coding:
    - 🟠 Orange: Medications
    - 🔵 Blue: Medical exams
    - 🟡 Yellow: Legal milestones
    - 🔴 Red: Delivery/critical dates
    - ⚪ Gray: Custom/other
    """

    MEDICATION = "medication"
    MEDICAL_EXAM = "medical_exam"
    LEGAL = "legal"
    DELIVERY = "delivery"
    CUSTOM = "custom"


class MatchEventPerson(str, Enum):
    """
    Who the match event is for.

    Color coding:
    - 🟢 Green: IP events
    - 🟣 Purple: Surrogate events
    """

    SURROGATE = "surrogate"
    IP = "ip"


class NotificationType(str, Enum):
    """Types of in-app notifications."""

    # Surrogate notifications
    SURROGATE_ASSIGNED = "surrogate_assigned"
    SURROGATE_STATUS_CHANGED = "surrogate_status_changed"
    SURROGATE_CLAIM_AVAILABLE = "surrogate_claim_available"

    # Task notifications
    TASK_ASSIGNED = "task_assigned"
    TASK_DUE_SOON = "task_due_soon"  # Due within 24h
    TASK_OVERDUE = "task_overdue"  # Past due date
    WORKFLOW_APPROVAL_REQUESTED = "workflow_approval_requested"
    STATUS_CHANGE_REQUESTED = "status_change_requested"
    STATUS_CHANGE_APPROVED = "status_change_approved"
    STATUS_CHANGE_REJECTED = "status_change_rejected"

    # Appointment notifications
    APPOINTMENT_REQUESTED = "appointment_requested"  # New appointment request
    APPOINTMENT_CONFIRMED = "appointment_confirmed"  # Appointment confirmed
    APPOINTMENT_CANCELLED = "appointment_cancelled"  # Appointment cancelled
    APPOINTMENT_REMINDER = "appointment_reminder"  # Reminder before appointment

    # Form notifications
    FORM_SUBMISSION_RECEIVED = "form_submission_received"  # Application submitted

    # Contact attempt reminders
    CONTACT_REMINDER = "contact_reminder"  # Reminder to follow up on case

    # Interview notifications
    INTERVIEW_TRANSCRIPTION_COMPLETED = "interview_transcription_completed"

    # Attachment notifications
    ATTACHMENT_INFECTED = "attachment_infected"


# Note: is_priority is a boolean field on Surrogate model, not an enum
# Default: False (normal), True (priority - shown with gold styling in UI)


class TaskType(str, Enum):
    """Types of tasks."""

    MEETING = "meeting"
    FOLLOW_UP = "follow_up"
    CONTACT = "contact"
    REVIEW = "review"
    MEDICATION = "medication"  # For medication schedules
    EXAM = "exam"  # For medical exams
    APPOINTMENT = "appointment"  # For appointments
    WORKFLOW_APPROVAL = "workflow_approval"  # Workflow action requiring approval
    OTHER = "other"


class TaskStatus(str, Enum):
    """
    Task status for workflow approvals and other tracked statuses.

    Standard tasks use is_completed boolean.
    Workflow approval tasks use this status enum for richer state tracking.
    """

    PENDING = "pending"  # Awaiting action
    IN_PROGRESS = "in_progress"  # Work started
    COMPLETED = "completed"  # Successfully completed
    DENIED = "denied"  # Explicitly denied (workflow approvals)
    EXPIRED = "expired"  # Timed out (workflow approvals)


class JobType(str, Enum):
    """Types of background jobs."""

    SEND_EMAIL = "send_email"
    REMINDER = "reminder"
    WEBHOOK_RETRY = "webhook_retry"
    NOTIFICATION = "notification"
    META_LEAD_FETCH = "meta_lead_fetch"
    META_CAPI_EVENT = "meta_capi_event"
    META_HIERARCHY_SYNC = "meta_hierarchy_sync"  # Sync campaigns/adsets/ads
    META_SPEND_SYNC = "meta_spend_sync"  # Sync daily spend data
    META_FORM_SYNC = "meta_form_sync"  # Sync form metadata
    WORKFLOW_SWEEP = "workflow_sweep"
    WORKFLOW_EMAIL = "workflow_email"
    CSV_IMPORT = "csv_import"  # Background CSV imports for large files
    EXPORT_GENERATION = "export_generation"
    ADMIN_EXPORT = "admin_export"
    DATA_PURGE = "data_purge"
    CAMPAIGN_SEND = "campaign_send"  # Bulk email campaign execution
    AI_CHAT = "ai_chat"
    CONTACT_REMINDER_CHECK = "contact_reminder_check"  # Daily contact follow-up check
    INTERVIEW_TRANSCRIPTION = "interview_transcription"
    ATTACHMENT_SCAN = "attachment_scan"
    WORKFLOW_APPROVAL_EXPIRY = "workflow_approval_expiry"  # Sweep for expired approvals
    WORKFLOW_RESUME = "workflow_resume"  # Resume workflow after approval resolution


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

    new → ready_to_match → matched → delivered
    Plus archive/restore pseudo-statuses for history tracking.
    """

    NEW = "new"
    READY_TO_MATCH = "ready_to_match"
    MATCHED = "matched"
    DELIVERED = "delivered"

    # Archive pseudo-statuses (for history tracking)
    ARCHIVED = "archived"
    RESTORED = "restored"


class EntityType(str, Enum):
    """Entity types for polymorphic relationships (e.g., notes)."""

    SURROGATE = "surrogate"
    INTENDED_PARENT = "intended_parent"


class OwnerType(str, Enum):
    """Owner type for surrogates - Salesforce-style single owner model."""

    USER = "user"
    QUEUE = "queue"


# =============================================================================
# Centralized Defaults (keep models, services, migrations in sync)
# =============================================================================

DEFAULT_SURROGATE_STATUS = SurrogateStatus.NEW_UNREAD
DEFAULT_SURROGATE_SOURCE = SurrogateSource.MANUAL
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
    META_HIERARCHY = "meta_hierarchy"  # Hierarchy sync health
    META_SPEND = "meta_spend"  # Spend sync health
    META_FORMS = "meta_forms"  # Forms sync health
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

    # Meta/Integration
    META_FETCH_FAILED = "meta_fetch_failed"
    META_CONVERT_FAILED = "meta_convert_failed"
    META_TOKEN_EXPIRING = "meta_token_expiring"
    META_TOKEN_EXPIRED = "meta_token_expired"
    META_API_ERROR = "meta_api_error"

    # Worker/Jobs
    WORKER_JOB_FAILED = "worker_job_failed"
    API_ERROR = "api_error"

    # Email
    EMAIL_SEND_FAILED = "email_send_failed"
    INVITE_SEND_FAILED = "invite_send_failed"

    # OAuth/Integration
    OAUTH_TOKEN_REFRESH_FAILED = "oauth_token_refresh_failed"
    INTEGRATION_API_ERROR = "integration_api_error"

    # Webhooks
    WEBHOOK_DELIVERY_FAILED = "webhook_delivery_failed"

    # Notifications
    NOTIFICATION_PUSH_FAILED = "notification_push_failed"

    # AI Services
    AI_PROVIDER_ERROR = "ai_provider_error"
    TRANSCRIPTION_FAILED = "transcription_failed"

    # Search
    SEARCH_QUERY_FAILED = "search_query_failed"

    # Workflow
    WORKFLOW_EXECUTION_FAILED = "workflow_execution_failed"


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

    SURROGATE_CREATED = "surrogate_created"
    STATUS_CHANGED = "status_changed"
    SURROGATE_ASSIGNED = "surrogate_assigned"
    SURROGATE_UPDATED = "surrogate_updated"
    TASK_DUE = "task_due"
    TASK_OVERDUE = "task_overdue"
    SCHEDULED = "scheduled"
    INACTIVITY = "inactivity"
    # Match triggers
    MATCH_PROPOSED = "match_proposed"
    MATCH_ACCEPTED = "match_accepted"
    MATCH_REJECTED = "match_rejected"
    # Document trigger
    DOCUMENT_UPLOADED = "document_uploaded"  # Fires after scan_status = 'clean'
    # Note trigger (high-volume, requires condition to activate)
    NOTE_ADDED = "note_added"
    # Appointment triggers
    APPOINTMENT_SCHEDULED = "appointment_scheduled"
    APPOINTMENT_COMPLETED = "appointment_completed"


class RecurrenceMode(str, Enum):
    """Recurrence mode for workflows."""

    ONE_TIME = "one_time"  # Fire once per entity per trigger event
    RECURRING = "recurring"  # Fire on schedule until resolved/stopped


class WorkflowActionType(str, Enum):
    """Actions a workflow can execute."""

    SEND_EMAIL = "send_email"
    CREATE_TASK = "create_task"
    ASSIGN_SURROGATE = "assign_surrogate"
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
    PAUSED = "paused"  # waiting for human approval
    CANCELED = "canceled"  # user denied approval or owner changed
    EXPIRED = "expired"  # approval timed out


class WorkflowEventSource(str, Enum):
    """Source that triggered a workflow event."""

    USER = "user"
    SYSTEM = "system"
    WORKFLOW = "workflow"


class CampaignStatus(str, Enum):
    """Status of a campaign."""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class CampaignRecipientStatus(str, Enum):
    """Status of a campaign recipient."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    SKIPPED = "skipped"


class FormStatus(str, Enum):
    """Status of a form configuration."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class FormSubmissionStatus(str, Enum):
    """Status of a submitted form response."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class SuppressionReason(str, Enum):
    """Reason for email suppression."""

    OPT_OUT = "opt_out"
    BOUNCED = "bounced"
    ARCHIVED = "archived"
    COMPLAINT = "complaint"


# =============================================================================
# Role Permission Helpers (avoid string literals, use enum values)
# =============================================================================

# Roles that can assign surrogates to other users
ROLES_CAN_ASSIGN = {Role.CASE_MANAGER, Role.ADMIN, Role.DEVELOPER}

# Roles that can archive/restore surrogates (all roles can archive their own surrogates)
ROLES_CAN_ARCHIVE = {
    Role.INTAKE_SPECIALIST,
    Role.CASE_MANAGER,
    Role.ADMIN,
    Role.DEVELOPER,
}

# Roles that can hard-delete surrogates (requires is_archived=true)
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
    DATA_EXPORT_SURROGATES = "data_export_surrogates"
    DATA_EXPORT_ANALYTICS = "data_export_analytics"
    DATA_EXPORT_CONFIG = "data_export_config"
    DATA_VIEW_SURROGATE = "data_view_surrogate"
    DATA_VIEW_NOTE = "data_view_note"
    PHI_VIEWED = "phi_viewed"
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

    # Forms
    FORM_SUBMISSION_RECEIVED = "form_submission_received"
    FORM_SUBMISSION_APPROVED = "form_submission_approved"
    FORM_SUBMISSION_REJECTED = "form_submission_rejected"
    FORM_SUBMISSION_FILE_DOWNLOADED = "form_submission_file_downloaded"

    # Tasks
    TASK_DELETED = "task_deleted"


# =============================================================================
# Appointments & Scheduling
# =============================================================================


class MeetingMode(str, Enum):
    """Meeting mode for appointments."""

    ZOOM = "zoom"
    GOOGLE_MEET = "google_meet"
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

    PENDING = "pending"  # Awaiting approval
    CONFIRMED = "confirmed"  # Approved, scheduled
    COMPLETED = "completed"  # Meeting took place
    CANCELLED = "cancelled"  # Cancelled by client or staff
    NO_SHOW = "no_show"  # Client didn't show up
    EXPIRED = "expired"  # Pending request expired before approval


class AppointmentEmailType(str, Enum):
    """Types of emails sent for appointments."""

    REQUEST_RECEIVED = "request_received"
    CONFIRMED = "confirmed"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    REMINDER = "reminder"


# Default appointment status
DEFAULT_APPOINTMENT_STATUS = AppointmentStatus.PENDING


# =============================================================================
# Contact Attempts Tracking
# =============================================================================


class ContactMethod(str, Enum):
    """Contact methods - can select multiple per attempt."""

    PHONE = "phone"
    EMAIL = "email"
    SMS = "sms"


class ContactOutcome(str, Enum):
    """Outcome of a contact attempt."""

    REACHED = "reached"
    NO_ANSWER = "no_answer"
    VOICEMAIL = "voicemail"
    WRONG_NUMBER = "wrong_number"
    EMAIL_BOUNCED = "email_bounced"


class ContactStatus(str, Enum):
    """Surrogate-level contact status for reminder logic."""

    UNREACHED = "unreached"
    REACHED = "reached"
