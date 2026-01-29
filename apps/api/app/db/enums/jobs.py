"""Job-related enums."""

from enum import Enum


class JobType(str, Enum):
    """Types of background jobs."""

    SEND_EMAIL = "send_email"
    REMINDER = "reminder"
    WEBHOOK_RETRY = "webhook_retry"
    NOTIFICATION = "notification"
    META_LEAD_FETCH = "meta_lead_fetch"
    META_LEAD_REPROCESS_FORM = "meta_lead_reprocess_form"
    META_CAPI_EVENT = "meta_capi_event"
    META_HIERARCHY_SYNC = "meta_hierarchy_sync"  # Sync campaigns/adsets/ads
    META_SPEND_SYNC = "meta_spend_sync"  # Sync daily spend data
    META_FORM_SYNC = "meta_form_sync"  # Sync form metadata
    ZAPIER_STAGE_EVENT = "zapier_stage_event"
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
    ORG_DELETE = "org_delete"  # Hard delete org after grace period


class JobStatus(str, Enum):
    """Status of background jobs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
