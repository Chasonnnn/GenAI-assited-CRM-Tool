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
