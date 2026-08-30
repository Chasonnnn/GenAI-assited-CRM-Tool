"""Compliance service - exports, redaction, retention, and legal holds."""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.util import find_spec
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.enums import JobStatus, JobType
from app.db.models import (
    AIActionApproval,
    AIConversation,
    AIEntitySummary,
    AIMessage,
    AIUsageLog,
    Attachment,
    AuditLog,
    Campaign,
    CampaignRecipient,
    DataRetentionPolicy,
    Donor,
    EmailDelivery,
    EmailLog,
    EmailMessage,
    EmailMessageContent,
    EmailMessageOccurrence,
    EntityNote,
    ExportJob,
    FormSubmission,
    FormSubmissionFile,
    IntakeLead,
    Job,
    LegalHold,
    Match,
    MessageDelivery,
    MessageMediaAsset,
    MessageMediaLink,
    MessageWebhookEvent,
    MessagingConsentEvidence,
    MessagingConsentState,
    MessagingContact,
    MessagingGlobalSuppression,
    MessagingMessage,
    MetaLead,
    Notification,
    Surrogate,
    SurrogateActivityLog,
    Task,
    Ticket,
    TicketEvent,
    TicketNote,
    User,
    WorkflowExecution,
)
from app.services import (
    audit_service,
    google_tasks_cleanup_service,
    job_service,
    storage_cleanup_service,
)
from app.utils.pagination import PaginationParams, paginate_query

EXPORT_STATUS_PENDING = "pending"
EXPORT_STATUS_PROCESSING = "processing"
EXPORT_STATUS_COMPLETED = "completed"
EXPORT_STATUS_FAILED = "failed"

REDACT_MODE_REDACTED = "redacted"
REDACT_MODE_FULL = "full"


PERSON_LINKED_TARGETS = {
    "donor",
    "surrogate",
    "intended_parent",
    "match",
    "task",
    "note",
    "entity_note",
    "surrogate_activity",
    "user",
}

PERSON_LINKED_DETAIL_KEYS = {
    "donor_id",
    "surrogate_id",
    "user_id",
    "intended_parent_id",
    "match_id",
    "task_id",
    "note_id",
    "email",
    "phone",
    "full_name",
}

DATE_REDACTION_FORMAT = "%Y-%m"

CSV_DANGEROUS_PREFIXES = ("=", "+", "-", "@")

logger = logging.getLogger(__name__)


EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PHONE_RE = re.compile(r"(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?(\d{4})")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _mask_email(value: str) -> str:
    match = EMAIL_RE.search(value)
    if not match:
        return "[REDACTED]"
    return f"***@{match.group(2)}"


def _mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "***-***-****"
    return f"***-***-{digits[-4:]}"


def _mask_ip(value: str) -> str:
    if ":" in value:
        # IPv6 - keep first 4 blocks
        blocks = value.split(":")
        return ":".join(blocks[:4] + ["x"] * max(0, 4 - len(blocks[:4])))
    parts = value.split(".")
    if len(parts) != 4:
        return "x.x.x.x"
    return f"{parts[0]}.{parts[1]}.x.x"


def _mask_name(value: str) -> str:
    value = value.strip()
    if not value:
        return "[REDACTED]"
    return f"{value[0]}. ***"


def _mask_id_last4(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "****"
    return f"***-**-{digits[-4:]}"


PHI_FIELDS = {
    "full_name": _mask_name,
    "actor_name": _mask_name,
    "email": _mask_email,
    "phone": _mask_phone,
    "fax": _mask_phone,
    "ip_address": _mask_ip,
    "ssn": _mask_id_last4,
    "mrn": _mask_id_last4,
    "account_number": _mask_id_last4,
    "address": lambda _: "[REDACTED]",
    "city": lambda _: "[REDACTED]",
    "zip_code": lambda v: f"{str(v)[:3]}**" if v else "[REDACTED]",
    "postal_code": lambda v: f"{str(v)[:3]}**" if v else "[REDACTED]",
    "device_id": lambda _: "[REDACTED]",
    "photo_url": lambda _: "[REMOVED]",
    "signature": lambda _: "[REMOVED]",
    "user_agent": lambda _: "[REDACTED]",
}

PHI_KEY_PATTERNS = [
    re.compile(r"email", re.IGNORECASE),
    re.compile(r"phone|fax", re.IGNORECASE),
    re.compile(r"ssn|mrn|account", re.IGNORECASE),
    re.compile(r"address|street|city|zip|postal", re.IGNORECASE),
    re.compile(r"ip_address|device", re.IGNORECASE),
    re.compile(r"full_name|first_name|last_name", re.IGNORECASE),
]

DATE_KEY_PATTERNS = [
    re.compile(r"dob|date_of_birth|birth", re.IGNORECASE),
    re.compile(r"created_at|updated_at|completed_at", re.IGNORECASE),
]


def _redact_free_text(text: str) -> str:
    def email_sub(match: re.Match) -> str:
        return f"***@{match.group(2)}"

    def phone_sub(match: re.Match) -> str:
        return f"***-***-{match.group(3)}"

    text = EMAIL_RE.sub(email_sub, text)
    text = PHONE_RE.sub(phone_sub, text)
    text = SSN_RE.sub("***-**-****", text)
    text = IPV4_RE.sub(lambda m: _mask_ip(m.group(0)), text)
    return text


def _is_person_linked(log: AuditLog) -> bool:
    if log.target_type and log.target_type in PERSON_LINKED_TARGETS:
        return True
    if log.actor_user_id:
        return True
    if log.details:
        for key in log.details.keys():
            if key in PERSON_LINKED_DETAIL_KEYS:
                return True
    return False


def _redact_datetime(value: datetime) -> str:
    return value.strftime(DATE_REDACTION_FORMAT)


def _redact_value(key: str, value: Any, person_linked: bool) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return {k: _redact_value(k, v, person_linked) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(key, v, person_linked) for v in value]
    if isinstance(value, datetime) and person_linked:
        return _redact_datetime(value)

    normalized_key = key.lower() if key else ""
    if person_linked and any(pattern.search(normalized_key) for pattern in DATE_KEY_PATTERNS):
        if isinstance(value, datetime):
            return _redact_datetime(value)
        if isinstance(value, str) and len(value) >= 7:
            return value[:7]
        return "[REDACTED]"
    if normalized_key in PHI_FIELDS:
        return PHI_FIELDS[normalized_key](str(value))
    if any(pattern.search(normalized_key) for pattern in PHI_KEY_PATTERNS):
        return "[REDACTED]"
    if isinstance(value, str):
        return _redact_free_text(value)
    return value


def _csv_safe(value: str) -> str:
    if value and value.startswith(CSV_DANGEROUS_PREFIXES):
        return f"'{value}"
    return value


def _serialize_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _serialize_json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize_json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_json_value(v) for v in value]
    return value


def _resolve_actor_names(db: Session, logs: list[AuditLog]) -> dict[UUID, str]:
    actor_ids = {log.actor_user_id for log in logs if log.actor_user_id}
    if not actor_ids:
        return {}
    actors = db.query(User).filter(User.id.in_(actor_ids)).all()
    return {actor.id: actor.display_name for actor in actors}


def _build_export_rows(
    db: Session, logs: list[AuditLog], redact_mode: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    actor_names = _resolve_actor_names(db, logs)
    rows: list[dict[str, Any]] = []

    range_start_prev_hash = logs[0].prev_hash if logs else None
    chain_contiguous = True
    last_hash = None

    for log in logs:
        if log.entry_hash is None:
            chain_contiguous = False
        if last_hash is not None and log.prev_hash != last_hash:
            chain_contiguous = False
        if last_hash is not None and log.prev_hash is None:
            chain_contiguous = False
        last_hash = log.entry_hash

        actor_name = actor_names.get(log.actor_user_id) if log.actor_user_id else None
        person_linked = _is_person_linked(log)

        row: dict[str, Any] = {
            "id": str(log.id),
            "organization_id": str(log.organization_id),
            "event_type": log.event_type,
            "actor_user_id": str(log.actor_user_id) if log.actor_user_id else None,
            "actor_name": actor_name,
            "target_type": log.target_type,
            "target_id": str(log.target_id) if log.target_id else None,
            "details": log.details or {},
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "request_id": str(log.request_id) if log.request_id else None,
            "prev_hash": log.prev_hash,
            "entry_hash": log.entry_hash,
            "before_version_id": str(log.before_version_id) if log.before_version_id else None,
            "after_version_id": str(log.after_version_id) if log.after_version_id else None,
            "created_at": log.created_at,
        }

        if redact_mode == REDACT_MODE_REDACTED:
            row = {k: _redact_value(k, v, person_linked) for k, v in row.items()}
            if person_linked and isinstance(row.get("created_at"), datetime):
                row["created_at"] = _redact_datetime(row["created_at"])
        rows.append(row)

    metadata = {
        "range_start_prev_hash": range_start_prev_hash,
        "chain_contiguous": chain_contiguous,
    }
    return rows, metadata


def _ensure_local_export_dir(org_id: UUID) -> str:
    base_dir = os.path.abspath(settings.EXPORT_LOCAL_DIR)
    export_dir = os.path.join(base_dir, str(org_id))
    os.makedirs(export_dir, exist_ok=True)
    return export_dir


def _require_boto3() -> None:
    if find_spec("boto3") is None:
        raise RuntimeError("boto3 is required for S3 export storage")


def _upload_to_s3(file_path: str, key: str) -> None:
    _require_boto3()
    if not settings.EXPORT_S3_BUCKET:
        raise RuntimeError("EXPORT_S3_BUCKET must be set for S3 exports")

    from app.services import storage_client

    client = storage_client.get_export_s3_client()
    client.upload_file(file_path, settings.EXPORT_S3_BUCKET, key)


def _generate_s3_url(file_path: str) -> str:
    _require_boto3()
    if not settings.EXPORT_S3_BUCKET:
        raise RuntimeError("EXPORT_S3_BUCKET must be set for S3 exports")

    from app.services import storage_client

    client = storage_client.get_export_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.EXPORT_S3_BUCKET, "Key": file_path},
        ExpiresIn=settings.EXPORT_URL_TTL_SECONDS,
    )


def generate_s3_download_url(file_path: str) -> str:
    """Public wrapper for generating a signed S3 download URL."""
    return _generate_s3_url(file_path)


def _build_export_key(org_id: UUID, filename: str) -> str:
    prefix = settings.EXPORT_S3_PREFIX.strip("/")
    return f"{prefix}/{org_id}/{filename}"


def _write_metadata_file(path: str, metadata: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, sort_keys=True)


def create_export_job(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    export_type: str,
    start_date: datetime,
    end_date: datetime,
    file_format: str,
    redact_mode: str,
    acknowledgment: str | None,
) -> ExportJob:
    if start_date >= end_date:
        raise ValueError("start_date must be before end_date")

    one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    recent_exports = (
        db.scalar(
            select(func.count(ExportJob.id)).where(
                ExportJob.organization_id == org_id,
                ExportJob.created_at >= one_hour_ago,
            )
        )
        or 0
    )
    if recent_exports >= settings.EXPORT_RATE_LIMIT_PER_HOUR:
        raise ValueError("Export rate limit exceeded")

    log_count = (
        db.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.organization_id == org_id,
                AuditLog.created_at >= start_date,
                AuditLog.created_at <= end_date,
            )
        )
        or 0
    )
    if log_count > settings.EXPORT_MAX_RECORDS:
        raise ValueError("Export exceeds maximum record limit")

    job = ExportJob(
        organization_id=org_id,
        created_by_user_id=user_id,
        status=EXPORT_STATUS_PENDING,
        export_type=export_type,
        format=file_format,
        redact_mode=redact_mode,
        date_range_start=start_date,
        date_range_end=end_date,
        record_count=None,
        acknowledgment=acknowledgment,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    job_service.schedule_job(
        db=db,
        org_id=org_id,
        job_type=JobType.EXPORT_GENERATION,
        payload={"export_job_id": str(job.id), "user_id": str(user_id)},
    )

    audit_service.log_compliance_export_requested(
        db=db,
        org_id=org_id,
        user_id=user_id,
        export_job_id=job.id,
        export_type=export_type,
        record_count=log_count,
        redact_mode=redact_mode,
        file_format=file_format,
    )
    db.commit()

    return job


def list_export_jobs(db: Session, org_id: UUID, limit: int = 50) -> list[ExportJob]:
    return (
        db.query(ExportJob)
        .filter(ExportJob.organization_id == org_id)
        .order_by(ExportJob.created_at.desc())
        .limit(limit)
        .all()
    )


def get_export_job(db: Session, org_id: UUID, export_job_id: UUID) -> ExportJob | None:
    return (
        db.query(ExportJob)
        .filter(
            ExportJob.organization_id == org_id,
            ExportJob.id == export_job_id,
        )
        .first()
    )


def generate_download_url(job: ExportJob) -> str | None:
    if job.status != EXPORT_STATUS_COMPLETED or not job.file_path:
        return None
    if settings.EXPORT_STORAGE_BACKEND == "s3":
        return _generate_s3_url(job.file_path)
    return f"/audit/exports/{job.id}/download"


def _write_csv(file_path: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        header = []
    else:
        header = list(rows[0].keys())

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if header:
            writer.writerow(header)
        for row in rows:
            serialized = [_csv_safe(_serialize_value(row.get(key))) for key in header]
            writer.writerow(serialized)


def _write_json(file_path: str, rows: list[dict[str, Any]]) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("[\n")
        for idx, row in enumerate(rows):
            if idx > 0:
                f.write(",\n")
            f.write(json.dumps(_serialize_json_value(row), sort_keys=True))
        f.write("\n]")


def process_export_job(db: Session, export_job_id: UUID) -> ExportJob:
    job = db.query(ExportJob).filter(ExportJob.id == export_job_id).first()
    if not job:
        raise ValueError("Export job not found")

    job.status = EXPORT_STATUS_PROCESSING
    db.commit()

    try:
        logs = (
            db.query(AuditLog)
            .filter(
                AuditLog.organization_id == job.organization_id,
                AuditLog.created_at >= job.date_range_start,
                AuditLog.created_at <= job.date_range_end,
            )
            .order_by(AuditLog.created_at, AuditLog.id)
            .all()
        )

        rows, chain_metadata = _build_export_rows(db, logs, job.redact_mode)

        redacted = job.redact_mode == REDACT_MODE_REDACTED
        metadata = {
            "export_id": str(job.id),
            "created_at": datetime.now(UTC).isoformat(),
            "redacted": redacted,
            "date_redaction": "year_month" if redacted else "none",
            "chain_verifiable": False if redacted else chain_metadata["chain_contiguous"],
            "chain_contiguous": chain_metadata["chain_contiguous"],
            "range_start_prev_hash": chain_metadata["range_start_prev_hash"],
            "record_count": len(rows),
            "disclaimer": "Redacted export. Original hashes included for reference only."
            if redacted
            else "Full export.",
        }

        filename = f"audit_export_{job.id}.{job.format}"
        metadata_filename = f"audit_export_{job.id}.metadata.json"

        if settings.EXPORT_STORAGE_BACKEND == "s3":
            with tempfile.TemporaryDirectory() as temp_dir:
                file_path = os.path.join(temp_dir, filename)
                metadata_path = os.path.join(temp_dir, metadata_filename)
                if job.format == "csv":
                    _write_csv(file_path, rows)
                else:
                    _write_json(file_path, rows)
                _write_metadata_file(metadata_path, metadata)

                key = _build_export_key(job.organization_id, filename)
                meta_key = _build_export_key(job.organization_id, metadata_filename)
                _upload_to_s3(file_path, key)
                _upload_to_s3(metadata_path, meta_key)
                job.file_path = key
        else:
            export_dir = _ensure_local_export_dir(job.organization_id)
            file_path = os.path.join(export_dir, filename)
            metadata_path = os.path.join(export_dir, metadata_filename)
            if job.format == "csv":
                _write_csv(file_path, rows)
            else:
                _write_json(file_path, rows)
            _write_metadata_file(metadata_path, metadata)
            job.file_path = os.path.relpath(file_path, os.path.abspath(settings.EXPORT_LOCAL_DIR))

        job.record_count = len(rows)
        job.status = EXPORT_STATUS_COMPLETED
        job.completed_at = datetime.now(UTC)
        db.commit()
        db.refresh(job)
        return job
    except Exception as exc:
        job.status = EXPORT_STATUS_FAILED
        job.error_message = str(exc)
        db.commit()
        raise


def resolve_local_export_path(file_path: str) -> str:
    base_dir = os.path.abspath(settings.EXPORT_LOCAL_DIR)
    resolved_path = os.path.abspath(os.path.join(base_dir, file_path))
    try:
        is_within_base = os.path.commonpath([resolved_path, base_dir]) == base_dir
    except ValueError as exc:
        raise ValueError("Resolved export path is outside export directory") from exc
    if not is_within_base:
        raise ValueError("Resolved export path is outside export directory")
    return resolved_path


def list_retention_policies(db: Session, org_id: UUID) -> list[DataRetentionPolicy]:
    return (
        db.query(DataRetentionPolicy)
        .filter(DataRetentionPolicy.organization_id == org_id)
        .order_by(DataRetentionPolicy.entity_type)
        .all()
    )


def seed_default_retention_policies(
    db: Session,
    org_id: UUID,
) -> list[DataRetentionPolicy]:
    """Create default retention policies for a new organization."""
    default_entities: list[tuple[str, int]] = [
        ("donors", settings.DEFAULT_RETENTION_DAYS),
        ("donor_leads", settings.DEFAULT_RETENTION_DAYS),
        ("surrogates", settings.DEFAULT_RETENTION_DAYS),
        ("matches", settings.DEFAULT_RETENTION_DAYS),
        ("tasks", settings.DEFAULT_RETENTION_DAYS),
        ("entity_notes", settings.DEFAULT_RETENTION_DAYS),
        ("surrogate_activity", settings.DEFAULT_RETENTION_DAYS),
        ("ai_conversations", settings.DEFAULT_RETENTION_DAYS),
        ("ai_messages", settings.DEFAULT_RETENTION_DAYS),
        ("ai_action_approvals", settings.DEFAULT_RETENTION_DAYS),
        ("ai_usage_log", settings.DEFAULT_RETENTION_DAYS),
        ("ai_entity_summaries", settings.DEFAULT_RETENTION_DAYS),
        # Ticketing/Gmail ingestion entities use 7-year retention by default.
        ("tickets", 2557),
        ("ticket_events", 2557),
        ("ticket_notes", 2557),
        ("email_messages", 2557),
        ("email_message_contents", 2557),
        ("email_message_occurrences", 2557),
        ("messaging_messages", 2557),
        ("messaging_consent_evidence", 2557),
        ("messaging_webhook_events", 2557),
        ("messaging_media_assets", 2557),
    ]
    existing = {policy.entity_type for policy in list_retention_policies(db, org_id)}
    created: list[DataRetentionPolicy] = []
    for entity_type, retention_days in default_entities:
        if entity_type in existing:
            continue
        policy = DataRetentionPolicy(
            organization_id=org_id,
            entity_type=entity_type,
            retention_days=retention_days,
            is_active=True,
            created_by_user_id=None,
        )
        db.add(policy)
        created.append(policy)
    if created:
        db.commit()
        for policy in created:
            db.refresh(policy)
    return created


def upsert_retention_policy(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    entity_type: str,
    retention_days: int,
    is_active: bool,
) -> DataRetentionPolicy:
    if entity_type == "audit_logs":
        raise ValueError("audit_logs are archive-only and cannot be purged")
    policy = (
        db.query(DataRetentionPolicy)
        .filter(
            DataRetentionPolicy.organization_id == org_id,
            DataRetentionPolicy.entity_type == entity_type,
        )
        .first()
    )
    if policy:
        policy.retention_days = retention_days
        policy.is_active = is_active
    else:
        policy = DataRetentionPolicy(
            organization_id=org_id,
            entity_type=entity_type,
            retention_days=retention_days,
            is_active=is_active,
            created_by_user_id=user_id,
        )
        db.add(policy)
    db.commit()
    db.refresh(policy)

    audit_service.log_compliance_retention_updated(
        db=db,
        org_id=org_id,
        user_id=user_id,
        policy_id=policy.id,
        entity_type=entity_type,
        retention_days=retention_days,
        is_active=is_active,
    )
    db.commit()
    return policy


def list_legal_holds(
    db: Session,
    org_id: UUID,
    pagination: PaginationParams,
) -> tuple[list[LegalHold], int]:
    query = (
        db.query(LegalHold)
        .filter(LegalHold.organization_id == org_id)
        .order_by(LegalHold.created_at.desc())
    )
    return paginate_query(query, pagination)


def create_legal_hold(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    entity_type: str | None,
    entity_id: UUID | None,
    reason: str,
) -> LegalHold:
    hold = LegalHold(
        organization_id=org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        reason=reason,
        created_by_user_id=user_id,
    )
    db.add(hold)
    db.commit()
    db.refresh(hold)

    audit_service.log_compliance_legal_hold_created(
        db=db,
        org_id=org_id,
        user_id=user_id,
        hold_id=hold.id,
        entity_type=entity_type,
        entity_id=entity_id,
        reason=reason,
    )
    db.commit()
    return hold


def release_legal_hold(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    hold_id: UUID,
) -> LegalHold | None:
    hold = (
        db.query(LegalHold)
        .filter(
            LegalHold.organization_id == org_id,
            LegalHold.id == hold_id,
            LegalHold.released_at.is_(None),
        )
        .first()
    )
    if not hold:
        return None
    hold.released_at = datetime.now(UTC)
    hold.released_by_user_id = user_id
    db.commit()
    db.refresh(hold)

    audit_service.log_compliance_legal_hold_released(
        db=db,
        org_id=org_id,
        user_id=user_id,
        hold_id=hold.id,
        entity_type=hold.entity_type,
        entity_id=hold.entity_id,
    )
    db.commit()
    return hold


def _get_active_legal_holds(
    db: Session, org_id: UUID
) -> tuple[bool, set[UUID], dict[str, set[UUID]]]:
    holds = (
        db.query(LegalHold)
        .filter(
            LegalHold.organization_id == org_id,
            LegalHold.released_at.is_(None),
        )
        .all()
    )
    org_hold = any(hold.entity_type is None for hold in holds)
    surrogate_hold_ids = {
        hold.entity_id for hold in holds if hold.entity_type == "surrogate" and hold.entity_id
    }
    entity_hold_ids: dict[str, set[UUID]] = {}
    for hold in holds:
        if hold.entity_type and hold.entity_id:
            entity_hold_ids.setdefault(hold.entity_type, set()).add(hold.entity_id)
    return org_hold, surrogate_hold_ids, entity_hold_ids


@dataclass
class PurgeResult:
    entity_type: str
    count: int


def _build_retention_query(
    db: Session,
    org_id: UUID,
    entity_type: str,
    cutoff: datetime,
    surrogate_hold_ids: set[UUID],
    entity_hold_ids: dict[str, set[UUID]],
):
    if entity_type == "donors":
        query = db.query(Donor).filter(
            Donor.organization_id == org_id,
            Donor.archived_at.is_not(None),
            Donor.archived_at < cutoff,
        )
        if entity_hold_ids.get("donor"):
            query = query.filter(~Donor.id.in_(entity_hold_ids["donor"]))
        if entity_hold_ids.get("task"):
            held_task_exists = (
                select(Task.id)
                .where(
                    Task.donor_id == Donor.id,
                    Task.id.in_(entity_hold_ids["task"]),
                )
                .exists()
            )
            query = query.filter(~held_task_exists)
        if entity_hold_ids.get("attachment"):
            held_attachment_ids = entity_hold_ids["attachment"]
            held_attachment_exists = (
                select(Attachment.id)
                .where(
                    Attachment.donor_id == Donor.id,
                    Attachment.id.in_(held_attachment_ids),
                )
                .exists()
            )
            query = query.filter(
                ~held_attachment_exists,
                or_(
                    Donor.profile_photo_attachment_id.is_(None),
                    ~Donor.profile_photo_attachment_id.in_(held_attachment_ids),
                ),
            )
        if entity_hold_ids.get("form_submission"):
            query = query.filter(
                ~select(FormSubmission.id)
                .where(
                    FormSubmission.donor_id == Donor.id,
                    FormSubmission.id.in_(entity_hold_ids["form_submission"]),
                )
                .exists()
            )
        if entity_hold_ids.get("form_submission_file"):
            query = query.filter(
                ~select(FormSubmissionFile.id)
                .join(
                    FormSubmission,
                    FormSubmissionFile.submission_id == FormSubmission.id,
                )
                .where(
                    FormSubmission.organization_id == Donor.organization_id,
                    FormSubmission.donor_id == Donor.id,
                    FormSubmissionFile.organization_id == Donor.organization_id,
                    FormSubmissionFile.id.in_(entity_hold_ids["form_submission_file"]),
                )
                .exists()
            )
        if entity_hold_ids.get("intake_lead"):
            query = query.filter(
                ~select(IntakeLead.id)
                .where(
                    IntakeLead.promoted_donor_id == Donor.id,
                    IntakeLead.id.in_(entity_hold_ids["intake_lead"]),
                )
                .exists()
            )
        if entity_hold_ids.get("meta_lead"):
            query = query.filter(
                ~select(MetaLead.id)
                .where(
                    MetaLead.converted_donor_id == Donor.id,
                    MetaLead.id.in_(entity_hold_ids["meta_lead"]),
                )
                .exists()
            )
        note_hold_ids = set().union(
            entity_hold_ids.get("entity_notes", set()),
            entity_hold_ids.get("entity_note", set()),
            entity_hold_ids.get("note", set()),
        )
        if note_hold_ids:
            query = query.filter(
                ~select(EntityNote.id)
                .where(
                    EntityNote.organization_id == Donor.organization_id,
                    EntityNote.entity_type == "donor",
                    EntityNote.entity_id == Donor.id,
                    EntityNote.id.in_(note_hold_ids),
                )
                .exists()
            )
        if entity_hold_ids.get("workflow_execution"):
            query = query.filter(
                ~select(WorkflowExecution.id)
                .where(
                    WorkflowExecution.organization_id == Donor.organization_id,
                    WorkflowExecution.subject_type.in_(("egg_donor", "sperm_donor")),
                    WorkflowExecution.subject_id == Donor.id,
                    WorkflowExecution.id.in_(entity_hold_ids["workflow_execution"]),
                )
                .exists()
            )
        return query
    if entity_type == "surrogates":
        query = db.query(Surrogate).filter(
            Surrogate.organization_id == org_id,
            Surrogate.archived_at.is_not(None),
            Surrogate.archived_at < cutoff,
        )
        if surrogate_hold_ids:
            query = query.filter(~Surrogate.id.in_(surrogate_hold_ids))
        return query
    if entity_type == "matches":
        query = db.query(Match).filter(
            Match.organization_id == org_id,
            Match.created_at < cutoff,
        )
        if surrogate_hold_ids:
            query = query.filter(~Match.surrogate_id.in_(surrogate_hold_ids))
        if entity_hold_ids.get("match"):
            query = query.filter(~Match.id.in_(entity_hold_ids["match"]))
        return query
    if entity_type == "tasks":
        query = db.query(Task).filter(
            Task.organization_id == org_id,
            Task.is_completed.is_(True),
            Task.completed_at.is_not(None),
            Task.completed_at < cutoff,
        )
        if surrogate_hold_ids:
            query = query.filter(
                or_(Task.surrogate_id.is_(None), ~Task.surrogate_id.in_(surrogate_hold_ids))
            )
        if entity_hold_ids.get("donor"):
            query = query.filter(
                or_(Task.donor_id.is_(None), ~Task.donor_id.in_(entity_hold_ids["donor"]))
            )
        if entity_hold_ids.get("task"):
            query = query.filter(~Task.id.in_(entity_hold_ids["task"]))
        return query
    if entity_type == "entity_notes":
        query = db.query(EntityNote).filter(
            EntityNote.organization_id == org_id,
            EntityNote.created_at < cutoff,
        )
        if surrogate_hold_ids:
            query = query.filter(
                or_(
                    EntityNote.entity_type != "surrogate",
                    ~EntityNote.entity_id.in_(surrogate_hold_ids),
                )
            )
        protected_notes = []
        for hold_entity_type, hold_ids in entity_hold_ids.items():
            if not hold_ids:
                continue
            if hold_entity_type == "entity_notes":
                protected_notes.append(EntityNote.id.in_(hold_ids))
            else:
                protected_notes.append(
                    and_(
                        EntityNote.entity_type == hold_entity_type,
                        EntityNote.entity_id.in_(hold_ids),
                    )
                )
        if protected_notes:
            query = query.filter(~or_(*protected_notes))
        return query
    if entity_type == "surrogate_activity":
        query = db.query(SurrogateActivityLog).filter(
            SurrogateActivityLog.organization_id == org_id,
            SurrogateActivityLog.created_at < cutoff,
        )
        if surrogate_hold_ids:
            query = query.filter(~SurrogateActivityLog.surrogate_id.in_(surrogate_hold_ids))
        if entity_hold_ids.get("surrogate_activity"):
            query = query.filter(
                ~SurrogateActivityLog.id.in_(entity_hold_ids["surrogate_activity"])
            )
        return query
    if entity_type == "ai_conversations":
        query = db.query(AIConversation).filter(
            AIConversation.organization_id == org_id,
            AIConversation.updated_at < cutoff,
        )
        if surrogate_hold_ids:
            query = query.filter(
                or_(
                    ~AIConversation.entity_type.in_(("surrogate", "case")),
                    ~AIConversation.entity_id.in_(surrogate_hold_ids),
                )
            )
        if entity_hold_ids.get("ai_conversation"):
            query = query.filter(~AIConversation.id.in_(entity_hold_ids["ai_conversation"]))
        return query
    if entity_type == "ai_messages":
        query = (
            db.query(AIMessage)
            .join(AIConversation, AIMessage.conversation_id == AIConversation.id)
            .filter(
                AIConversation.organization_id == org_id,
                AIMessage.created_at < cutoff,
            )
        )
        if surrogate_hold_ids:
            query = query.filter(
                or_(
                    ~AIConversation.entity_type.in_(("surrogate", "case")),
                    ~AIConversation.entity_id.in_(surrogate_hold_ids),
                )
            )
        if entity_hold_ids.get("ai_message"):
            query = query.filter(~AIMessage.id.in_(entity_hold_ids["ai_message"]))
        return query
    if entity_type == "ai_action_approvals":
        query = (
            db.query(AIActionApproval)
            .join(AIMessage, AIActionApproval.message_id == AIMessage.id)
            .join(AIConversation, AIMessage.conversation_id == AIConversation.id)
            .filter(
                AIConversation.organization_id == org_id,
                AIActionApproval.created_at < cutoff,
            )
        )
        if surrogate_hold_ids:
            query = query.filter(
                or_(
                    ~AIConversation.entity_type.in_(("surrogate", "case")),
                    ~AIConversation.entity_id.in_(surrogate_hold_ids),
                )
            )
        if entity_hold_ids.get("ai_action_approval"):
            query = query.filter(~AIActionApproval.id.in_(entity_hold_ids["ai_action_approval"]))
        return query
    if entity_type == "ai_usage_log":
        query = (
            db.query(AIUsageLog)
            .outerjoin(AIConversation, AIUsageLog.conversation_id == AIConversation.id)
            .filter(
                AIUsageLog.organization_id == org_id,
                AIUsageLog.created_at < cutoff,
            )
        )
        if surrogate_hold_ids:
            query = query.filter(
                or_(
                    AIConversation.id.is_(None),
                    ~AIConversation.entity_type.in_(("surrogate", "case")),
                    ~AIConversation.entity_id.in_(surrogate_hold_ids),
                )
            )
        if entity_hold_ids.get("ai_usage_log"):
            query = query.filter(~AIUsageLog.id.in_(entity_hold_ids["ai_usage_log"]))
        return query
    if entity_type == "ai_entity_summaries":
        query = db.query(AIEntitySummary).filter(
            AIEntitySummary.organization_id == org_id,
            AIEntitySummary.updated_at < cutoff,
        )
        if surrogate_hold_ids:
            query = query.filter(
                or_(
                    ~AIEntitySummary.entity_type.in_(("surrogate", "case")),
                    ~AIEntitySummary.entity_id.in_(surrogate_hold_ids),
                )
            )
        if entity_hold_ids.get("ai_entity_summary"):
            query = query.filter(~AIEntitySummary.id.in_(entity_hold_ids["ai_entity_summary"]))
        return query
    if entity_type == "tickets":
        query = db.query(Ticket).filter(
            Ticket.organization_id == org_id,
            Ticket.updated_at < cutoff,
        )
        if surrogate_hold_ids:
            query = query.filter(
                or_(Ticket.surrogate_id.is_(None), ~Ticket.surrogate_id.in_(surrogate_hold_ids))
            )
        if entity_hold_ids.get("ticket"):
            query = query.filter(~Ticket.id.in_(entity_hold_ids["ticket"]))
        return query
    if entity_type == "ticket_events":
        query = (
            db.query(TicketEvent)
            .join(Ticket, Ticket.id == TicketEvent.ticket_id)
            .filter(
                TicketEvent.organization_id == org_id,
                TicketEvent.created_at < cutoff,
            )
        )
        if surrogate_hold_ids:
            query = query.filter(
                or_(Ticket.surrogate_id.is_(None), ~Ticket.surrogate_id.in_(surrogate_hold_ids))
            )
        if entity_hold_ids.get("ticket_event"):
            query = query.filter(~TicketEvent.id.in_(entity_hold_ids["ticket_event"]))
        return query
    if entity_type == "ticket_notes":
        query = (
            db.query(TicketNote)
            .join(Ticket, Ticket.id == TicketNote.ticket_id)
            .filter(
                TicketNote.organization_id == org_id,
                TicketNote.created_at < cutoff,
            )
        )
        if surrogate_hold_ids:
            query = query.filter(
                or_(Ticket.surrogate_id.is_(None), ~Ticket.surrogate_id.in_(surrogate_hold_ids))
            )
        if entity_hold_ids.get("ticket_note"):
            query = query.filter(~TicketNote.id.in_(entity_hold_ids["ticket_note"]))
        return query
    if entity_type == "email_messages":
        query = db.query(EmailMessage).filter(
            EmailMessage.organization_id == org_id,
            EmailMessage.created_at < cutoff,
        )
        if entity_hold_ids.get("email_message"):
            query = query.filter(~EmailMessage.id.in_(entity_hold_ids["email_message"]))
        return query
    if entity_type == "email_message_contents":
        query = (
            db.query(EmailMessageContent)
            .join(EmailMessage, EmailMessage.id == EmailMessageContent.message_id)
            .filter(
                EmailMessageContent.organization_id == org_id,
                EmailMessageContent.parsed_at < cutoff,
            )
        )
        if entity_hold_ids.get("email_message_content"):
            query = query.filter(
                ~EmailMessageContent.id.in_(entity_hold_ids["email_message_content"])
            )
        return query
    if entity_type == "email_message_occurrences":
        query = db.query(EmailMessageOccurrence).filter(
            EmailMessageOccurrence.organization_id == org_id,
            EmailMessageOccurrence.created_at < cutoff,
        )
        if surrogate_hold_ids:
            held_ticket_ids = (
                db.query(Ticket.id)
                .filter(
                    Ticket.organization_id == org_id,
                    Ticket.surrogate_id.in_(surrogate_hold_ids),
                )
                .subquery()
            )
            query = query.filter(
                or_(
                    EmailMessageOccurrence.ticket_id.is_(None),
                    ~EmailMessageOccurrence.ticket_id.in_(held_ticket_ids),
                )
            )
        if entity_hold_ids.get("email_message_occurrence"):
            query = query.filter(
                ~EmailMessageOccurrence.id.in_(entity_hold_ids["email_message_occurrence"])
            )
        return query
    if entity_type == "messaging_messages":
        query = db.query(MessagingMessage).filter(
            MessagingMessage.organization_id == org_id,
            MessagingMessage.created_at < cutoff,
        )
        if surrogate_hold_ids:
            held_contact_ids = select(MessagingContact.id).where(
                MessagingContact.organization_id == org_id,
                MessagingContact.surrogate_id.in_(surrogate_hold_ids),
            )
            query = query.filter(~MessagingMessage.contact_id.in_(held_contact_ids))
        if entity_hold_ids.get("messaging_message"):
            query = query.filter(~MessagingMessage.id.in_(entity_hold_ids["messaging_message"]))
        return query
    if entity_type == "messaging_consent_evidence":
        backs_consent_state = (
            select(MessagingConsentState.id)
            .where(
                MessagingConsentState.organization_id == org_id,
                MessagingConsentState.latest_evidence_id == MessagingConsentEvidence.id,
            )
            .exists()
        )
        backs_global_suppression = (
            select(MessagingGlobalSuppression.id)
            .where(
                MessagingGlobalSuppression.organization_id == org_id,
                MessagingGlobalSuppression.latest_evidence_id == MessagingConsentEvidence.id,
            )
            .exists()
        )
        backs_delivery = (
            select(MessageDelivery.id)
            .where(
                MessageDelivery.organization_id == org_id,
                MessageDelivery.consent_evidence_id == MessagingConsentEvidence.id,
            )
            .exists()
        )
        query = db.query(MessagingConsentEvidence).filter(
            MessagingConsentEvidence.organization_id == org_id,
            MessagingConsentEvidence.created_at < cutoff,
            ~backs_consent_state,
            ~backs_global_suppression,
            ~backs_delivery,
        )
        if surrogate_hold_ids:
            held_contact_ids = select(MessagingContact.id).where(
                MessagingContact.organization_id == org_id,
                MessagingContact.surrogate_id.in_(surrogate_hold_ids),
            )
            query = query.filter(~MessagingConsentEvidence.contact_id.in_(held_contact_ids))
        if entity_hold_ids.get("messaging_consent_evidence"):
            query = query.filter(
                ~MessagingConsentEvidence.id.in_(entity_hold_ids["messaging_consent_evidence"])
            )
        return query
    if entity_type == "messaging_webhook_events":
        query = db.query(MessageWebhookEvent).filter(
            MessageWebhookEvent.organization_id == org_id,
            MessageWebhookEvent.received_at < cutoff,
        )
        if entity_hold_ids.get("messaging_webhook_event"):
            query = query.filter(
                ~MessageWebhookEvent.id.in_(entity_hold_ids["messaging_webhook_event"])
            )
        return query
    if entity_type == "messaging_media_assets":
        linked = (
            select(MessageMediaLink.id)
            .where(MessageMediaLink.media_asset_id == MessageMediaAsset.id)
            .exists()
        )
        query = db.query(MessageMediaAsset).filter(
            MessageMediaAsset.organization_id == org_id,
            MessageMediaAsset.created_at < cutoff,
            ~linked,
        )
        if entity_hold_ids.get("messaging_media_asset"):
            query = query.filter(
                ~MessageMediaAsset.id.in_(entity_hold_ids["messaging_media_asset"])
            )
        return query
    raise ValueError(f"Unsupported retention entity type: {entity_type}")


def preview_purge(db: Session, org_id: UUID) -> list[PurgeResult]:
    org_hold, surrogate_hold_ids, entity_hold_ids = _get_active_legal_holds(db, org_id)
    if org_hold:
        return []
    policies = list_retention_policies(db, org_id)
    results: list[PurgeResult] = []
    for policy in policies:
        if not policy.is_active or policy.retention_days == 0:
            continue
        cutoff = datetime.now(UTC) - timedelta(days=policy.retention_days)
        if policy.entity_type == "donor_leads":
            candidates = _get_donor_lead_purge_candidates(
                db,
                org_id=org_id,
                cutoff=cutoff,
                entity_hold_ids=entity_hold_ids,
            )
            results.append(PurgeResult(entity_type=policy.entity_type, count=candidates.count))
            continue
        query = _build_retention_query(
            db, org_id, policy.entity_type, cutoff, surrogate_hold_ids, entity_hold_ids
        )
        results.append(PurgeResult(entity_type=policy.entity_type, count=query.count()))
    return results


DONOR_SUBJECT_TYPES = ("egg_donor", "sperm_donor")


@dataclass(frozen=True, slots=True)
class _DonorLeadPurgeCandidates:
    submission_ids: frozenset[UUID]
    intake_lead_ids: frozenset[UUID]
    meta_lead_ids: frozenset[UUID]

    @property
    def count(self) -> int:
        return len(self.submission_ids) + len(self.intake_lead_ids) + len(self.meta_lead_ids)


def _ensure_email_deliveries_not_leased(
    db: Session,
    *,
    org_id: UUID,
    email_log_ids: set[UUID],
) -> None:
    if not email_log_ids:
        return
    deliveries = (
        db.query(EmailDelivery.id, EmailDelivery.status)
        .filter(
            EmailDelivery.organization_id == org_id,
            EmailDelivery.email_log_id.in_(email_log_ids),
        )
        .with_for_update()
        .all()
    )
    if any(status == "leased" for _delivery_id, status in deliveries):
        raise ValueError(
            "Cannot purge donors while a donor email delivery is leased; stop workers and retry"
        )


def _ensure_message_deliveries_not_leased(
    db: Session,
    *,
    org_id: UUID,
    message_delivery_ids: set[UUID],
) -> None:
    if not message_delivery_ids:
        return
    deliveries = (
        db.query(MessageDelivery.id, MessageDelivery.status)
        .filter(
            MessageDelivery.organization_id == org_id,
            MessageDelivery.id.in_(message_delivery_ids),
        )
        .with_for_update()
        .all()
    )
    if any(status == "leased" for _delivery_id, status in deliveries):
        raise ValueError(
            "Cannot purge donors while a donor message delivery is leased; stop workers and retry"
        )


def _get_donor_lead_purge_candidates(
    db: Session,
    *,
    org_id: UUID,
    cutoff: datetime,
    entity_hold_ids: dict[str, set[UUID]],
) -> _DonorLeadPurgeCandidates:
    """Resolve old, unconverted donor intake records without splitting linked pairs."""
    submission_query = db.query(FormSubmission.id).filter(
        FormSubmission.organization_id == org_id,
        FormSubmission.lead_kind.in_(DONOR_SUBJECT_TYPES),
        FormSubmission.donor_id.is_(None),
        FormSubmission.submitted_at < cutoff,
    )
    if entity_hold_ids.get("form_submission"):
        submission_query = submission_query.filter(
            ~FormSubmission.id.in_(entity_hold_ids["form_submission"])
        )
    submission_ids = {value for (value,) in submission_query.all()}

    intake_query = db.query(IntakeLead.id).filter(
        IntakeLead.organization_id == org_id,
        IntakeLead.lead_type.in_(DONOR_SUBJECT_TYPES),
        IntakeLead.promoted_donor_id.is_(None),
        IntakeLead.created_at < cutoff,
    )
    if entity_hold_ids.get("intake_lead"):
        intake_query = intake_query.filter(~IntakeLead.id.in_(entity_hold_ids["intake_lead"]))
    intake_lead_ids = {value for (value,) in intake_query.all()}

    meta_query = db.query(MetaLead.id).filter(
        MetaLead.organization_id == org_id,
        MetaLead.lead_kind.in_(DONOR_SUBJECT_TYPES),
        MetaLead.converted_donor_id.is_(None),
        MetaLead.received_at < cutoff,
    )
    if entity_hold_ids.get("meta_lead"):
        meta_query = meta_query.filter(~MetaLead.id.in_(entity_hold_ids["meta_lead"]))
    meta_lead_ids = {value for (value,) in meta_query.all()}

    held_file_ids = entity_hold_ids.get("form_submission_file", set())
    if held_file_ids and submission_ids:
        held_file_submission_ids = {
            value
            for (value,) in db.query(FormSubmissionFile.submission_id)
            .filter(
                FormSubmissionFile.organization_id == org_id,
                FormSubmissionFile.id.in_(held_file_ids),
                FormSubmissionFile.submission_id.in_(submission_ids),
            )
            .all()
        }
        submission_ids.difference_update(held_file_submission_ids)

    held_execution_ids = entity_hold_ids.get("workflow_execution", set())
    if held_execution_ids:
        held_executions = (
            db.query(
                WorkflowExecution.entity_type,
                WorkflowExecution.entity_id,
                WorkflowExecution.subject_type,
                WorkflowExecution.subject_id,
            )
            .filter(
                WorkflowExecution.organization_id == org_id,
                WorkflowExecution.id.in_(held_execution_ids),
            )
            .all()
        )
        for entity_type, entity_id, subject_type, subject_id in held_executions:
            for candidate_type, candidate_id in (
                (entity_type, entity_id),
                (subject_type, subject_id),
            ):
                if candidate_type == "form_submission":
                    submission_ids.discard(candidate_id)
                elif candidate_type == "intake_lead":
                    intake_lead_ids.discard(candidate_id)
                elif candidate_type == "meta_lead":
                    meta_lead_ids.discard(candidate_id)

    linked_pairs = {
        (intake_id, submission_id)
        for intake_id, submission_id in db.query(
            IntakeLead.id,
            IntakeLead.form_submission_id,
        )
        .filter(
            IntakeLead.organization_id == org_id,
            IntakeLead.lead_type.in_(DONOR_SUBJECT_TYPES),
            IntakeLead.promoted_donor_id.is_(None),
            IntakeLead.form_submission_id.is_not(None),
            or_(
                IntakeLead.id.in_(intake_lead_ids),
                IntakeLead.form_submission_id.in_(submission_ids),
            ),
        )
        .all()
    }
    linked_pairs.update(
        (intake_id, submission_id)
        for submission_id, intake_id in db.query(
            FormSubmission.id,
            FormSubmission.intake_lead_id,
        )
        .filter(
            FormSubmission.organization_id == org_id,
            FormSubmission.lead_kind.in_(DONOR_SUBJECT_TYPES),
            FormSubmission.donor_id.is_(None),
            FormSubmission.intake_lead_id.is_not(None),
            or_(
                FormSubmission.id.in_(submission_ids),
                FormSubmission.intake_lead_id.in_(intake_lead_ids),
            ),
        )
        .all()
    )
    for intake_id, submission_id in linked_pairs:
        if intake_id not in intake_lead_ids or submission_id not in submission_ids:
            intake_lead_ids.discard(intake_id)
            submission_ids.discard(submission_id)

    return _DonorLeadPurgeCandidates(
        submission_ids=frozenset(submission_ids),
        intake_lead_ids=frozenset(intake_lead_ids),
        meta_lead_ids=frozenset(meta_lead_ids),
    )


def _donor_related_jobs(
    db: Session,
    *,
    org_id: UUID,
    donor_ids: set[UUID],
    task_ids: set[UUID],
    attachment_ids: set[UUID],
    submission_ids: set[UUID],
    submission_file_ids: set[UUID],
    intake_lead_ids: set[UUID],
    meta_lead_ids: set[UUID],
    meta_external_ids: set[str],
    execution_ids: set[UUID],
) -> tuple[set[UUID], set[UUID]]:
    """Resolve jobs whose payload can retain or act on donor PII."""
    donor_id_strings = {str(value) for value in donor_ids}
    task_id_strings = {str(value) for value in task_ids}
    attachment_id_strings = {str(value) for value in attachment_ids}
    submission_id_strings = {str(value) for value in submission_ids}
    submission_file_id_strings = {str(value) for value in submission_file_ids}
    intake_lead_id_strings = {str(value) for value in intake_lead_ids}
    meta_lead_id_strings = {str(value) for value in meta_lead_ids}
    execution_id_strings = {str(value) for value in execution_ids}
    relevant_types = {
        JobType.ATTACHMENT_SCAN.value,
        JobType.FORM_SUBMISSION_FILE_SCAN.value,
        JobType.META_LEAD_FETCH.value,
        JobType.NOTIFICATION.value,
        JobType.WORKFLOW_EMAIL.value,
        JobType.WORKFLOW_RESUME.value,
    }
    jobs = (
        db.query(Job)
        .filter(
            Job.organization_id == org_id,
            Job.job_type.in_(relevant_types),
        )
        .with_for_update()
        .all()
    )
    matched_job_ids: set[UUID] = set()
    workflow_email_job_ids: set[UUID] = set()
    for job in jobs:
        payload = job.payload or {}
        entity_type = payload.get("entity_type")
        entity_id = str(payload.get("entity_id") or "")
        execution_id = str(
            payload.get("workflow_execution_id") or payload.get("execution_id") or ""
        )
        related = False
        if job.job_type == JobType.WORKFLOW_EMAIL.value:
            related = (
                payload.get("subject_type") in DONOR_SUBJECT_TYPES
                and str(payload.get("subject_id") or "") in donor_id_strings
            ) or execution_id in execution_id_strings
        elif job.job_type == JobType.WORKFLOW_RESUME.value:
            related = execution_id in execution_id_strings
        elif job.job_type == JobType.ATTACHMENT_SCAN.value:
            related = str(payload.get("attachment_id") or "") in attachment_id_strings
        elif job.job_type == JobType.FORM_SUBMISSION_FILE_SCAN.value:
            related = str(payload.get("submission_file_id") or "") in submission_file_id_strings
        elif job.job_type == JobType.META_LEAD_FETCH.value:
            related = str(payload.get("leadgen_id") or "") in meta_external_ids
        elif job.job_type == JobType.NOTIFICATION.value:
            related = (
                entity_type in {"donor", *DONOR_SUBJECT_TYPES} and entity_id in donor_id_strings
            ) or (entity_type == "task" and entity_id in task_id_strings)
            related = related or (
                entity_type == "form_submission" and entity_id in submission_id_strings
            )
            related = related or (
                entity_type == "intake_lead" and entity_id in intake_lead_id_strings
            )
            related = related or (entity_type == "meta_lead" and entity_id in meta_lead_id_strings)
        if not related:
            continue
        if job.status == JobStatus.RUNNING.value:
            raise ValueError(
                "Cannot purge donors while a donor-related background job is running; "
                "stop workers and retry"
            )
        matched_job_ids.add(job.id)
        if job.job_type == JobType.WORKFLOW_EMAIL.value:
            workflow_email_job_ids.add(job.id)

    campaign_jobs = (
        db.query(Job)
        .filter(
            Job.organization_id == org_id,
            Job.job_type == JobType.CAMPAIGN_SEND.value,
        )
        .with_for_update()
        .all()
    )
    running_campaign_ids: set[UUID] = set()
    for job in campaign_jobs:
        if job.status != JobStatus.RUNNING.value:
            continue
        try:
            running_campaign_ids.add(UUID(str((job.payload or {}).get("campaign_id"))))
        except (TypeError, ValueError):
            continue
    if running_campaign_ids:
        donor_campaign_running = (
            db.query(Campaign.id)
            .filter(
                Campaign.organization_id == org_id,
                Campaign.id.in_(running_campaign_ids),
                Campaign.recipient_type.in_(DONOR_SUBJECT_TYPES),
            )
            .first()
        )
        if donor_campaign_running is not None:
            raise ValueError(
                "Cannot purge donors while a donor campaign is running; stop workers and retry"
            )
    return matched_job_ids, workflow_email_job_ids


def _purge_donor_leads(
    db: Session,
    *,
    org_id: UUID,
    candidates: _DonorLeadPurgeCandidates,
    storage_keys_to_delete: list[str],
) -> int:
    """Remove old unconverted donor applications and their derived PII."""
    if candidates.count == 0:
        return 0

    submission_ids = set(candidates.submission_ids)
    intake_lead_ids = set(candidates.intake_lead_ids)
    meta_lead_ids = set(candidates.meta_lead_ids)
    submission_file_rows = []
    if submission_ids:
        submission_file_rows = (
            db.query(FormSubmissionFile.id, FormSubmissionFile.storage_key)
            .filter(
                FormSubmissionFile.organization_id == org_id,
                FormSubmissionFile.submission_id.in_(submission_ids),
            )
            .all()
        )
        storage_keys_to_delete.extend(key for _file_id, key in submission_file_rows)
    submission_file_ids = {file_id for file_id, _key in submission_file_rows}

    meta_lead_rows = []
    if meta_lead_ids:
        meta_lead_rows = (
            db.query(MetaLead.id, MetaLead.meta_lead_id)
            .filter(
                MetaLead.organization_id == org_id,
                MetaLead.id.in_(meta_lead_ids),
            )
            .all()
        )
    meta_external_ids = {external_id for _lead_id, external_id in meta_lead_rows}

    execution_filters = []
    for entity_type, entity_ids in (
        ("form_submission", submission_ids),
        ("intake_lead", intake_lead_ids),
        ("meta_lead", meta_lead_ids),
    ):
        if not entity_ids:
            continue
        execution_filters.extend(
            (
                and_(
                    WorkflowExecution.entity_type == entity_type,
                    WorkflowExecution.entity_id.in_(entity_ids),
                ),
                and_(
                    WorkflowExecution.subject_type == entity_type,
                    WorkflowExecution.subject_id.in_(entity_ids),
                ),
            )
        )
    execution_ids = {
        value
        for (value,) in db.query(WorkflowExecution.id)
        .filter(
            WorkflowExecution.organization_id == org_id,
            or_(*execution_filters),
        )
        .all()
    }

    job_ids, workflow_email_job_ids = _donor_related_jobs(
        db,
        org_id=org_id,
        donor_ids=set(),
        task_ids=set(),
        attachment_ids=set(),
        submission_ids=submission_ids,
        submission_file_ids=submission_file_ids,
        intake_lead_ids=intake_lead_ids,
        meta_lead_ids=meta_lead_ids,
        meta_external_ids=meta_external_ids,
        execution_ids=execution_ids,
    )
    email_log_ids: set[UUID] = set()
    if workflow_email_job_ids:
        email_log_ids = {
            value
            for (value,) in db.query(EmailLog.id)
            .filter(
                EmailLog.organization_id == org_id,
                or_(
                    EmailLog.job_id.in_(workflow_email_job_ids),
                    and_(
                        EmailLog.source_type == "workflow_job",
                        EmailLog.source_id.in_(workflow_email_job_ids),
                    ),
                ),
            )
            .all()
        }
    _ensure_email_deliveries_not_leased(
        db,
        org_id=org_id,
        email_log_ids=email_log_ids,
    )

    notification_filters = []
    for entity_type, entity_ids in (
        ("form_submission", submission_ids),
        ("intake_lead", intake_lead_ids),
        ("meta_lead", meta_lead_ids),
        ("workflow_execution", execution_ids),
    ):
        if entity_ids:
            notification_filters.append(
                and_(
                    Notification.entity_type == entity_type, Notification.entity_id.in_(entity_ids)
                )
            )
    if notification_filters:
        db.query(Notification).filter(
            Notification.organization_id == org_id,
            or_(*notification_filters),
        ).delete(synchronize_session=False)
    if email_log_ids:
        db.query(EmailLog).filter(
            EmailLog.organization_id == org_id,
            EmailLog.id.in_(email_log_ids),
        ).delete(synchronize_session=False)
    if job_ids:
        db.query(Job).filter(
            Job.organization_id == org_id,
            Job.id.in_(job_ids),
        ).delete(synchronize_session=False)
    if execution_ids:
        db.query(WorkflowExecution).filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.id.in_(execution_ids),
        ).delete(synchronize_session=False)
    if meta_lead_ids:
        db.query(MetaLead).filter(
            MetaLead.organization_id == org_id,
            MetaLead.id.in_(meta_lead_ids),
        ).delete(synchronize_session=False)
    if intake_lead_ids:
        db.query(IntakeLead).filter(
            IntakeLead.organization_id == org_id,
            IntakeLead.id.in_(intake_lead_ids),
        ).delete(synchronize_session=False)
    if submission_ids:
        db.query(FormSubmission).filter(
            FormSubmission.organization_id == org_id,
            FormSubmission.id.in_(submission_ids),
        ).delete(synchronize_session=False)
    return candidates.count


def _purge_donor_dependents(
    db: Session,
    *,
    org_id: UUID,
    donor_ids: list[UUID],
    profile_photo_ids: list[UUID],
    storage_keys_to_delete: list[str],
) -> None:
    """Remove donor-linked source and derived PII before the donor rows cascade."""
    if not donor_ids:
        return
    donor_id_set = set(donor_ids)
    task_ids = {
        value
        for (value,) in db.query(Task.id)
        .filter(Task.organization_id == org_id, Task.donor_id.in_(donor_ids))
        .all()
    }
    google_tasks_cleanup_service.enqueue_donor_task_remote_deletions(
        db,
        org_id=org_id,
        task_ids=task_ids,
    )
    attachment_rows = (
        db.query(Attachment.id, Attachment.storage_key)
        .filter(
            Attachment.organization_id == org_id,
            or_(
                Attachment.donor_id.in_(donor_ids),
                Attachment.id.in_(profile_photo_ids),
            ),
        )
        .all()
    )
    attachment_ids = {attachment_id for attachment_id, _key in attachment_rows}
    storage_keys_to_delete.extend(key for _attachment_id, key in attachment_rows)

    submission_ids = {
        value
        for (value,) in db.query(FormSubmission.id)
        .filter(
            FormSubmission.organization_id == org_id,
            FormSubmission.donor_id.in_(donor_ids),
        )
        .all()
    }
    submission_file_rows = []
    if submission_ids:
        submission_file_rows = (
            db.query(FormSubmissionFile.id, FormSubmissionFile.storage_key)
            .filter(
                FormSubmissionFile.organization_id == org_id,
                FormSubmissionFile.submission_id.in_(submission_ids),
            )
            .all()
        )
        storage_keys_to_delete.extend(key for _file_id, key in submission_file_rows)
    submission_file_ids = {file_id for file_id, _key in submission_file_rows}

    intake_filters = [IntakeLead.promoted_donor_id.in_(donor_ids)]
    if submission_ids:
        intake_filters.append(IntakeLead.form_submission_id.in_(submission_ids))
    intake_lead_ids = {
        value
        for (value,) in db.query(IntakeLead.id)
        .filter(IntakeLead.organization_id == org_id, or_(*intake_filters))
        .all()
    }
    meta_lead_rows = (
        db.query(MetaLead.id, MetaLead.meta_lead_id)
        .filter(
            MetaLead.organization_id == org_id,
            MetaLead.converted_donor_id.in_(donor_ids),
        )
        .all()
    )
    meta_lead_ids = {lead_id for lead_id, _external_id in meta_lead_rows}
    meta_external_ids = {external_id for _lead_id, external_id in meta_lead_rows}
    note_ids = {
        value
        for (value,) in db.query(EntityNote.id)
        .filter(
            EntityNote.organization_id == org_id,
            EntityNote.entity_type == "donor",
            EntityNote.entity_id.in_(donor_ids),
        )
        .all()
    }

    execution_filters = [
        and_(
            WorkflowExecution.subject_type.in_(DONOR_SUBJECT_TYPES),
            WorkflowExecution.subject_id.in_(donor_ids),
        )
    ]
    for entity_type, entity_ids in (
        ("task", task_ids),
        ("note", note_ids),
        ("document", attachment_ids),
        ("form_submission", submission_ids),
        ("intake_lead", intake_lead_ids),
    ):
        if entity_ids:
            execution_filters.append(
                and_(
                    WorkflowExecution.entity_type == entity_type,
                    WorkflowExecution.entity_id.in_(entity_ids),
                )
            )
    execution_ids = {
        value
        for (value,) in db.query(WorkflowExecution.id)
        .filter(
            WorkflowExecution.organization_id == org_id,
            or_(*execution_filters),
        )
        .all()
    }

    campaign_recipient_rows = (
        db.query(
            CampaignRecipient.id,
            CampaignRecipient.email_log_id,
            CampaignRecipient.message_delivery_id,
        )
        .filter(
            CampaignRecipient.entity_type.in_(DONOR_SUBJECT_TYPES),
            CampaignRecipient.entity_id.in_(donor_ids),
        )
        .join(CampaignRecipient.run)
        .filter(CampaignRecipient.run.has(organization_id=org_id))
        .all()
    )
    campaign_recipient_ids = {row.id for row in campaign_recipient_rows}
    email_log_ids = {row.email_log_id for row in campaign_recipient_rows if row.email_log_id}
    message_delivery_ids = {
        row.message_delivery_id for row in campaign_recipient_rows if row.message_delivery_id
    }
    message_ids: set[UUID] = set()
    media_asset_ids: set[UUID] = set()
    if message_delivery_ids:
        message_ids = {
            value
            for (value,) in db.query(MessageDelivery.message_id)
            .filter(
                MessageDelivery.organization_id == org_id,
                MessageDelivery.id.in_(message_delivery_ids),
            )
            .all()
        }
        _ensure_message_deliveries_not_leased(
            db,
            org_id=org_id,
            message_delivery_ids=message_delivery_ids,
        )
    if message_ids:
        media_asset_ids = {
            value
            for (value,) in db.query(MessageMediaLink.media_asset_id)
            .filter(MessageMediaLink.message_id.in_(message_ids))
            .all()
        }

    job_ids, workflow_email_job_ids = _donor_related_jobs(
        db,
        org_id=org_id,
        donor_ids=donor_id_set,
        task_ids=task_ids,
        attachment_ids=attachment_ids,
        submission_ids=submission_ids,
        submission_file_ids=submission_file_ids,
        intake_lead_ids=intake_lead_ids,
        meta_lead_ids=meta_lead_ids,
        meta_external_ids=meta_external_ids,
        execution_ids=execution_ids,
    )
    if workflow_email_job_ids:
        email_log_ids.update(
            value
            for (value,) in db.query(EmailLog.id)
            .filter(
                EmailLog.organization_id == org_id,
                or_(
                    EmailLog.job_id.in_(workflow_email_job_ids),
                    and_(
                        EmailLog.source_type == "workflow_job",
                        EmailLog.source_id.in_(workflow_email_job_ids),
                    ),
                ),
            )
            .all()
        )

    _ensure_email_deliveries_not_leased(
        db,
        org_id=org_id,
        email_log_ids=email_log_ids,
    )

    notification_filters = [
        and_(
            Notification.entity_type.in_(("donor", *DONOR_SUBJECT_TYPES)),
            Notification.entity_id.in_(donor_ids),
        )
    ]
    for entity_type, entity_ids in (
        ("task", task_ids),
        ("workflow_execution", execution_ids),
        ("form_submission", submission_ids),
        ("intake_lead", intake_lead_ids),
        ("meta_lead", meta_lead_ids),
    ):
        if entity_ids:
            notification_filters.append(
                and_(
                    Notification.entity_type == entity_type, Notification.entity_id.in_(entity_ids)
                )
            )
    db.query(Notification).filter(
        Notification.organization_id == org_id,
        or_(*notification_filters),
    ).delete(synchronize_session=False)

    if campaign_recipient_ids:
        db.query(CampaignRecipient).filter(CampaignRecipient.id.in_(campaign_recipient_ids)).delete(
            synchronize_session=False
        )
    if email_log_ids:
        db.query(EmailLog).filter(
            EmailLog.organization_id == org_id,
            EmailLog.id.in_(email_log_ids),
        ).delete(synchronize_session=False)
    if message_ids:
        db.query(MessagingMessage).filter(
            MessagingMessage.organization_id == org_id,
            MessagingMessage.id.in_(message_ids),
        ).delete(synchronize_session=False)
    if media_asset_ids:
        orphan_media = (
            db.query(MessageMediaAsset.id, MessageMediaAsset.storage_key)
            .filter(
                MessageMediaAsset.organization_id == org_id,
                MessageMediaAsset.id.in_(media_asset_ids),
                ~select(MessageMediaLink.id)
                .where(MessageMediaLink.media_asset_id == MessageMediaAsset.id)
                .exists(),
            )
            .all()
        )
        storage_keys_to_delete.extend(key for _asset_id, key in orphan_media)
        orphan_media_ids = [asset_id for asset_id, _key in orphan_media]
        if orphan_media_ids:
            db.query(MessageMediaAsset).filter(MessageMediaAsset.id.in_(orphan_media_ids)).delete(
                synchronize_session=False
            )
    if job_ids:
        db.query(Job).filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
    if execution_ids:
        db.query(WorkflowExecution).filter(
            WorkflowExecution.organization_id == org_id,
            WorkflowExecution.id.in_(execution_ids),
        ).delete(synchronize_session=False)
    if note_ids:
        db.query(EntityNote).filter(
            EntityNote.organization_id == org_id,
            EntityNote.id.in_(note_ids),
        ).delete(synchronize_session=False)
    if meta_lead_ids:
        db.query(MetaLead).filter(
            MetaLead.organization_id == org_id,
            MetaLead.id.in_(meta_lead_ids),
        ).delete(synchronize_session=False)
    if intake_lead_ids:
        db.query(IntakeLead).filter(
            IntakeLead.organization_id == org_id,
            IntakeLead.id.in_(intake_lead_ids),
        ).delete(synchronize_session=False)
    if submission_ids:
        db.query(FormSubmission).filter(
            FormSubmission.organization_id == org_id,
            FormSubmission.id.in_(submission_ids),
        ).delete(synchronize_session=False)

    # The donor rows are locked by execute_purge, so no new FK reference can
    # commit. Rescan under task row locks immediately before the parent delete
    # to prove every remotely synced task has a durable deletion tombstone.
    final_task_ids = {
        value
        for (value,) in db.query(Task.id)
        .filter(Task.organization_id == org_id, Task.donor_id.in_(donor_ids))
        .with_for_update()
        .all()
    }
    google_tasks_cleanup_service.enqueue_donor_task_remote_deletions(
        db,
        org_id=org_id,
        task_ids=final_task_ids,
    )


def execute_purge(db: Session, org_id: UUID, user_id: UUID | None) -> list[PurgeResult]:
    org_hold, surrogate_hold_ids, entity_hold_ids = _get_active_legal_holds(db, org_id)
    if org_hold:
        return []
    policies = list_retention_policies(db, org_id)
    results: list[PurgeResult] = []
    storage_keys_to_delete: list[str] = []
    for policy in policies:
        if not policy.is_active or policy.retention_days == 0:
            continue
        cutoff = datetime.now(UTC) - timedelta(days=policy.retention_days)
        if policy.entity_type == "donor_leads":
            candidates = _get_donor_lead_purge_candidates(
                db,
                org_id=org_id,
                cutoff=cutoff,
                entity_hold_ids=entity_hold_ids,
            )
            count = _purge_donor_leads(
                db,
                org_id=org_id,
                candidates=candidates,
                storage_keys_to_delete=storage_keys_to_delete,
            )
            results.append(PurgeResult(entity_type=policy.entity_type, count=count))
            continue
        query = _build_retention_query(
            db, org_id, policy.entity_type, cutoff, surrogate_hold_ids, entity_hold_ids
        )
        count = query.count()
        if count:
            if policy.entity_type == "messaging_media_assets":
                storage_keys_to_delete.extend(
                    key for (key,) in query.with_entities(MessageMediaAsset.storage_key).all()
                )
                query.delete(synchronize_session=False)
            elif policy.entity_type == "donors":
                donor_rows = (
                    query.with_entities(
                        Donor.id,
                        Donor.profile_photo_attachment_id,
                    )
                    .with_for_update()
                    .all()
                )
                donor_ids = [donor_id for donor_id, _photo_id in donor_rows]
                count = len(donor_ids)
                profile_photo_ids = [
                    photo_id for _donor_id, photo_id in donor_rows if photo_id is not None
                ]
                _purge_donor_dependents(
                    db,
                    org_id=org_id,
                    donor_ids=donor_ids,
                    profile_photo_ids=profile_photo_ids,
                    storage_keys_to_delete=storage_keys_to_delete,
                )
                if donor_ids:
                    # Delete only the rows in the locked snapshot. A donor that
                    # becomes retention-eligible concurrently waits for the next
                    # purge instead of bypassing dependent-task reconciliation.
                    db.query(Donor).filter(
                        Donor.organization_id == org_id,
                        Donor.id.in_(donor_ids),
                    ).delete(synchronize_session=False)
            elif policy.entity_type == "tasks":
                task_rows = query.with_entities(Task.id, Task.donor_id).all()
                task_ids = [task_id for task_id, _donor_id in task_rows]
                count = len(task_ids)
                if task_ids:
                    donor_task_ids = {
                        task_id for task_id, donor_id in task_rows if donor_id is not None
                    }
                    google_tasks_cleanup_service.enqueue_donor_task_remote_deletions(
                        db,
                        org_id=org_id,
                        task_ids=donor_task_ids,
                    )
                    db.query(Notification).filter(
                        Notification.organization_id == org_id,
                        Notification.entity_type == "task",
                        Notification.entity_id.in_(task_ids),
                    ).delete(synchronize_session=False)
                    # Keep deletion tied to the exact snapshot whose donor
                    # identities were fenced above.
                    db.query(Task).filter(
                        Task.organization_id == org_id,
                        Task.id.in_(task_ids),
                    ).delete(synchronize_session=False)
            else:
                query.delete(synchronize_session=False)
        results.append(PurgeResult(entity_type=policy.entity_type, count=count))
    storage_cleanup_service.enqueue_storage_deletions(
        db,
        org_id=org_id,
        storage_keys=storage_keys_to_delete,
    )
    db.commit()

    audit_service.log_compliance_purge_executed(
        db=db,
        org_id=org_id,
        user_id=user_id,
        results=results,
    )
    db.commit()
    return results
