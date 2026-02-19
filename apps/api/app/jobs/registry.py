"""Job handler registry."""

from __future__ import annotations

from typing import Awaitable, Callable, Mapping

from app.db.enums import JobType
from app.jobs.handlers import (
    ai,
    appointments,
    attachments,
    campaigns,
    data_purge,
    email,
    exports,
    form_submissions,
    imports,
    interviews,
    meta,
    notifications,
    orgs,
    reminders,
    webhooks,
    workflows,
    zapier,
)

JobHandler = Callable[[object, object], Awaitable[None]]

JOB_HANDLERS: Mapping[str, JobHandler] = {
    JobType.SEND_EMAIL.value: email.process_send_email,
    JobType.REMINDER.value: reminders.process_reminder,
    JobType.WEBHOOK_RETRY.value: webhooks.process_webhook_retry,
    JobType.NOTIFICATION.value: notifications.process_notification,
    JobType.META_LEAD_FETCH.value: meta.process_meta_lead_fetch,
    JobType.META_LEAD_REPROCESS_FORM.value: meta.process_meta_lead_reprocess_form,
    JobType.META_CAPI_EVENT.value: meta.process_meta_capi_event,
    JobType.WORKFLOW_EMAIL.value: email.process_workflow_email,
    JobType.WORKFLOW_SWEEP.value: workflows.process_workflow_sweep,
    JobType.CSV_IMPORT.value: imports.process_csv_import,
    JobType.EXPORT_GENERATION.value: exports.process_export_generation,
    JobType.ADMIN_EXPORT.value: exports.process_admin_export,
    JobType.DATA_PURGE.value: data_purge.process_data_purge,
    JobType.CAMPAIGN_SEND.value: campaigns.process_campaign_send,
    JobType.AI_CHAT.value: ai.process_ai_chat,
    JobType.INTERVIEW_TRANSCRIPTION.value: interviews.process_interview_transcription,
    JobType.ATTACHMENT_SCAN.value: attachments.process_attachment_scan,
    JobType.FORM_SUBMISSION_FILE_SCAN.value: form_submissions.process_form_submission_file_scan,
    JobType.WORKFLOW_APPROVAL_EXPIRY.value: workflows.process_workflow_approval_expiry,
    JobType.WORKFLOW_RESUME.value: workflows.process_workflow_resume,
    JobType.META_HIERARCHY_SYNC.value: meta.process_meta_hierarchy_sync,
    JobType.META_SPEND_SYNC.value: meta.process_meta_spend_sync,
    JobType.META_FORM_SYNC.value: meta.process_meta_form_sync,
    JobType.ORG_DELETE.value: orgs.process_org_delete,
    JobType.ZAPIER_STAGE_EVENT.value: zapier.process_zapier_stage_event,
    JobType.GOOGLE_CALENDAR_SYNC.value: appointments.process_google_calendar_sync,
    JobType.GOOGLE_CALENDAR_WATCH_REFRESH.value: appointments.process_google_calendar_watch_refresh,
}


def resolve_job_handler(job_type: str) -> JobHandler:
    handler = JOB_HANDLERS.get(job_type)
    if not handler:
        raise ValueError(f"Unknown job type: {job_type}")
    return handler
