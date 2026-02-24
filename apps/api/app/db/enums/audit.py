"""Audit and compliance enums."""

from enum import Enum


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
    DATA_EMAIL_SENT = "data_email_sent"
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
    INTEGRATION_TOKEN_REFRESHED = "integration_token_refreshed"  # nosec B105
    META_ASSETS_CONNECTED = "meta_assets_connected"

    # User management
    USER_INVITED = "user_invited"
    USER_ROLE_CHANGED = "user_role_changed"
    USER_DEACTIVATED = "user_deactivated"

    # Core CRM writes (semantic mutation events)
    SURROGATE_CREATED = "surrogate_created"
    SURROGATE_UPDATED = "surrogate_updated"
    SURROGATE_ARCHIVED = "surrogate_archived"
    SURROGATE_RESTORED = "surrogate_restored"
    SURROGATE_DELETED = "surrogate_deleted"
    SURROGATE_CLAIMED = "surrogate_claimed"
    SURROGATE_ASSIGNED = "surrogate_assigned"
    SURROGATE_BULK_ASSIGNED = "surrogate_bulk_assigned"

    INTENDED_PARENT_CREATED = "intended_parent_created"
    INTENDED_PARENT_UPDATED = "intended_parent_updated"
    INTENDED_PARENT_STATUS_CHANGED = "intended_parent_status_changed"
    INTENDED_PARENT_ARCHIVED = "intended_parent_archived"
    INTENDED_PARENT_RESTORED = "intended_parent_restored"
    INTENDED_PARENT_DELETED = "intended_parent_deleted"

    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    TASK_UNCOMPLETED = "task_uncompleted"
    TASK_BULK_COMPLETED = "task_bulk_completed"
    TASK_RESOLVED = "task_resolved"

    MATCH_PROPOSED = "match_proposed"
    MATCH_ACCEPTED = "match_accepted"
    MATCH_REJECTED = "match_rejected"
    MATCH_CANCELLED = "match_cancelled"

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

    # Generic fallback for authenticated mutation requests not explicitly instrumented
    API_MUTATION_FALLBACK = "api_mutation_fallback"
