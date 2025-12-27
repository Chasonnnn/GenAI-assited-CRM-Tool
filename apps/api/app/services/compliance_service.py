"""Compliance service - exports, redaction, retention, and legal holds."""

from __future__ import annotations

import csv
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.enums import JobType
from app.db.models import (
    AuditLog,
    Case,
    CaseActivityLog,
    DataRetentionPolicy,
    EntityNote,
    ExportJob,
    LegalHold,
    Match,
    Task,
    User,
)
from app.services import audit_service, job_service


EXPORT_STATUS_PENDING = "pending"
EXPORT_STATUS_PROCESSING = "processing"
EXPORT_STATUS_COMPLETED = "completed"
EXPORT_STATUS_FAILED = "failed"

REDACT_MODE_REDACTED = "redacted"
REDACT_MODE_FULL = "full"


PERSON_LINKED_TARGETS = {
    "case",
    "intended_parent",
    "match",
    "task",
    "note",
    "entity_note",
    "case_activity",
    "user",
}

PERSON_LINKED_DETAIL_KEYS = {
    "case_id",
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


def _build_export_rows(db: Session, logs: list[AuditLog], redact_mode: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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


def _upload_to_s3(file_path: str, key: str) -> None:
    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise RuntimeError("boto3 is required for S3 export storage") from exc
    if not settings.EXPORT_S3_BUCKET:
        raise RuntimeError("EXPORT_S3_BUCKET must be set for S3 exports")

    client = boto3.client("s3", region_name=settings.EXPORT_S3_REGION or None)
    client.upload_file(file_path, settings.EXPORT_S3_BUCKET, key)


def _generate_s3_url(file_path: str) -> str:
    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise RuntimeError("boto3 is required for S3 export storage") from exc
    if not settings.EXPORT_S3_BUCKET:
        raise RuntimeError("EXPORT_S3_BUCKET must be set for S3 exports")

    client = boto3.client("s3", region_name=settings.EXPORT_S3_REGION or None)
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

    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_exports = db.query(ExportJob).filter(
        ExportJob.organization_id == org_id,
        ExportJob.created_at >= one_hour_ago,
    ).count()
    if recent_exports >= settings.EXPORT_RATE_LIMIT_PER_HOUR:
        raise ValueError("Export rate limit exceeded")

    log_count = db.query(AuditLog).filter(
        AuditLog.organization_id == org_id,
        AuditLog.created_at >= start_date,
        AuditLog.created_at <= end_date,
    ).count()
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

    return job


def list_export_jobs(db: Session, org_id: UUID, limit: int = 50) -> list[ExportJob]:
    return db.query(ExportJob).filter(
        ExportJob.organization_id == org_id
    ).order_by(ExportJob.created_at.desc()).limit(limit).all()


def get_export_job(db: Session, org_id: UUID, export_job_id: UUID) -> ExportJob | None:
    return db.query(ExportJob).filter(
        ExportJob.organization_id == org_id,
        ExportJob.id == export_job_id,
    ).first()


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
        logs = db.query(AuditLog).filter(
            AuditLog.organization_id == job.organization_id,
            AuditLog.created_at >= job.date_range_start,
            AuditLog.created_at <= job.date_range_end,
        ).order_by(AuditLog.created_at, AuditLog.id).all()

        rows, chain_metadata = _build_export_rows(db, logs, job.redact_mode)

        redacted = job.redact_mode == REDACT_MODE_REDACTED
        metadata = {
            "export_id": str(job.id),
            "created_at": datetime.utcnow().isoformat(),
            "redacted": redacted,
            "date_redaction": "year_month" if redacted else "none",
            "chain_verifiable": False if redacted else chain_metadata["chain_contiguous"],
            "chain_contiguous": chain_metadata["chain_contiguous"],
            "range_start_prev_hash": chain_metadata["range_start_prev_hash"],
            "record_count": len(rows),
            "disclaimer": "Redacted export. Original hashes included for reference only." if redacted else "Full export.",
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
        job.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
        return job
    except Exception as exc:
        job.status = EXPORT_STATUS_FAILED
        job.error_message = str(exc)
        db.commit()
        raise


def resolve_local_export_path(file_path: str) -> str:
    return os.path.join(os.path.abspath(settings.EXPORT_LOCAL_DIR), file_path)


def list_retention_policies(db: Session, org_id: UUID) -> list[DataRetentionPolicy]:
    return db.query(DataRetentionPolicy).filter(
        DataRetentionPolicy.organization_id == org_id
    ).order_by(DataRetentionPolicy.entity_type).all()


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
    policy = db.query(DataRetentionPolicy).filter(
        DataRetentionPolicy.organization_id == org_id,
        DataRetentionPolicy.entity_type == entity_type,
    ).first()
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
    return policy


def list_legal_holds(db: Session, org_id: UUID) -> list[LegalHold]:
    return db.query(LegalHold).filter(
        LegalHold.organization_id == org_id
    ).order_by(LegalHold.created_at.desc()).all()


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
    return hold


def release_legal_hold(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    hold_id: UUID,
) -> LegalHold | None:
    hold = db.query(LegalHold).filter(
        LegalHold.organization_id == org_id,
        LegalHold.id == hold_id,
        LegalHold.released_at.is_(None),
    ).first()
    if not hold:
        return None
    hold.released_at = datetime.utcnow()
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
    return hold


def _get_active_legal_holds(db: Session, org_id: UUID) -> tuple[bool, set[UUID], dict[str, set[UUID]]]:
    holds = db.query(LegalHold).filter(
        LegalHold.organization_id == org_id,
        LegalHold.released_at.is_(None),
    ).all()
    org_hold = any(hold.entity_type is None for hold in holds)
    case_hold_ids = {hold.entity_id for hold in holds if hold.entity_type == "case" and hold.entity_id}
    entity_hold_ids: dict[str, set[UUID]] = {}
    for hold in holds:
        if hold.entity_type and hold.entity_id:
            entity_hold_ids.setdefault(hold.entity_type, set()).add(hold.entity_id)
    return org_hold, case_hold_ids, entity_hold_ids


@dataclass
class PurgeResult:
    entity_type: str
    count: int


def _build_retention_query(
    db: Session,
    org_id: UUID,
    entity_type: str,
    cutoff: datetime,
    case_hold_ids: set[UUID],
    entity_hold_ids: dict[str, set[UUID]],
):
    if entity_type == "cases":
        query = db.query(Case).filter(
            Case.organization_id == org_id,
            Case.archived_at.is_not(None),
            Case.archived_at < cutoff,
        )
        if case_hold_ids:
            query = query.filter(~Case.id.in_(case_hold_ids))
        return query
    if entity_type == "matches":
        query = db.query(Match).filter(
            Match.organization_id == org_id,
            Match.created_at < cutoff,
        )
        if case_hold_ids:
            query = query.filter(~Match.case_id.in_(case_hold_ids))
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
        if case_hold_ids:
            query = query.filter(or_(Task.case_id.is_(None), ~Task.case_id.in_(case_hold_ids)))
        if entity_hold_ids.get("task"):
            query = query.filter(~Task.id.in_(entity_hold_ids["task"]))
        return query
    if entity_type == "entity_notes":
        query = db.query(EntityNote).filter(
            EntityNote.organization_id == org_id,
            EntityNote.created_at < cutoff,
        )
        if case_hold_ids:
            query = query.filter(
                or_(
                    EntityNote.entity_type != "case",
                    ~EntityNote.entity_id.in_(case_hold_ids),
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
    if entity_type == "case_activity":
        query = db.query(CaseActivityLog).filter(
            CaseActivityLog.organization_id == org_id,
            CaseActivityLog.created_at < cutoff,
        )
        if case_hold_ids:
            query = query.filter(~CaseActivityLog.case_id.in_(case_hold_ids))
        if entity_hold_ids.get("case_activity"):
            query = query.filter(~CaseActivityLog.id.in_(entity_hold_ids["case_activity"]))
        return query
    raise ValueError(f"Unsupported retention entity type: {entity_type}")


def preview_purge(db: Session, org_id: UUID) -> list[PurgeResult]:
    org_hold, case_hold_ids, entity_hold_ids = _get_active_legal_holds(db, org_id)
    if org_hold:
        return []
    policies = list_retention_policies(db, org_id)
    results: list[PurgeResult] = []
    for policy in policies:
        if not policy.is_active or policy.retention_days == 0:
            continue
        cutoff = datetime.utcnow() - timedelta(days=policy.retention_days)
        query = _build_retention_query(
            db, org_id, policy.entity_type, cutoff, case_hold_ids, entity_hold_ids
        )
        results.append(PurgeResult(entity_type=policy.entity_type, count=query.count()))
    return results


def execute_purge(db: Session, org_id: UUID, user_id: UUID | None) -> list[PurgeResult]:
    org_hold, case_hold_ids, entity_hold_ids = _get_active_legal_holds(db, org_id)
    if org_hold:
        return []
    policies = list_retention_policies(db, org_id)
    results: list[PurgeResult] = []
    for policy in policies:
        if not policy.is_active or policy.retention_days == 0:
            continue
        cutoff = datetime.utcnow() - timedelta(days=policy.retention_days)
        query = _build_retention_query(
            db, org_id, policy.entity_type, cutoff, case_hold_ids, entity_hold_ids
        )
        count = query.count()
        if count:
            query.delete(synchronize_session=False)
        results.append(PurgeResult(entity_type=policy.entity_type, count=count))
    db.commit()

    audit_service.log_compliance_purge_executed(
        db=db,
        org_id=org_id,
        user_id=user_id,
        results=results,
    )
    return results
