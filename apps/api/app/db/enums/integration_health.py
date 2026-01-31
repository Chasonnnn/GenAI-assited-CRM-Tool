"""Integration health and alert enums."""

from enum import Enum


class IntegrationType(str, Enum):
    """Types of integrations tracked for health monitoring."""

    META_LEADS = "meta_leads"
    META_CAPI = "meta_capi"
    META_HIERARCHY = "meta_hierarchy"  # Hierarchy sync health
    META_SPEND = "meta_spend"  # Spend sync health
    META_FORMS = "meta_forms"  # Forms sync health
    ZAPIER = "zapier"
    WORKER = "worker"


class IntegrationStatus(str, Enum):
    """Health status of an integration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"


class ConfigStatus(str, Enum):
    """Configuration status of an integration."""

    CONFIGURED = "configured"
    MISSING_TOKEN = "missing_token"  # nosec B105
    EXPIRED_TOKEN = "expired_token"  # nosec B105


class AlertType(str, Enum):
    """Types of system alerts."""

    # Meta/Integration
    META_FETCH_FAILED = "meta_fetch_failed"
    META_CONVERT_FAILED = "meta_convert_failed"
    META_TOKEN_EXPIRING = "meta_token_expiring"  # nosec B105
    META_TOKEN_EXPIRED = "meta_token_expired"  # nosec B105
    META_API_ERROR = "meta_api_error"

    # Worker/Jobs
    WORKER_JOB_FAILED = "worker_job_failed"
    API_ERROR = "api_error"

    # Email
    EMAIL_SEND_FAILED = "email_send_failed"
    INVITE_SEND_FAILED = "invite_send_failed"

    # OAuth/Integration
    OAUTH_TOKEN_REFRESH_FAILED = "oauth_token_refresh_failed"  # nosec B105
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
