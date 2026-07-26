"""Classify legacy running jobs for a safe worker-claim cutover."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.enums import AuditEventType, JobStatus


@dataclass(frozen=True, slots=True)
class LegacyJobReconciliationDecision:
    """One proposed terminal disposition for an expired legacy job."""

    job_id: UUID
    organization_id: UUID
    job_type: str
    run_at: datetime
    attempts: int
    evidence_flags: dict[str, bool]
    target_status: str
    reason_code: str
    non_replayable: bool


@dataclass(frozen=True, slots=True)
class LegacyJobReconciliationReport:
    """Stable, operator-reviewable result of one reconciliation pass."""

    mode: str
    fingerprint: str
    count: int
    residual_count: int
    decisions: tuple[LegacyJobReconciliationDecision, ...]
    evaluated_at: datetime
    applied_at: datetime | None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _fingerprint(
    decisions: tuple[LegacyJobReconciliationDecision, ...],
    *,
    stale_before: datetime,
    evaluated_at: datetime,
) -> str:
    canonical_plan = json.dumps(
        {
            "schema_version": 1,
            "stale_before": stale_before.isoformat(),
            "evaluated_at": evaluated_at.isoformat(),
            "decisions": [
                {
                    "job_id": str(decision.job_id),
                    "organization_id": str(decision.organization_id),
                    "job_type": decision.job_type,
                    "run_at": decision.run_at.isoformat(),
                    "attempts": decision.attempts,
                    "evidence_flags": decision.evidence_flags,
                    "target_status": decision.target_status,
                    "reason_code": decision.reason_code,
                    "non_replayable": decision.non_replayable,
                }
                for decision in sorted(decisions, key=lambda item: item.job_id)
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_plan.encode("utf-8")).hexdigest()


def _lockable_statement(sql: str, *, lock: bool):
    if lock:
        sql = f"{sql}\nFOR UPDATE OF job"
    return text(sql)


def _count_tokenless_running_jobs(db: Session) -> int:
    return db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM jobs
            WHERE status = 'running'
              AND (claim_token IS NULL OR claimed_at IS NULL)
            """
        )
    ).scalar_one()


def _classify_legacy_running_jobs(
    db: Session,
    *,
    stale_before: datetime,
    evaluated_at: datetime,
    lock: bool,
) -> tuple[LegacyJobReconciliationDecision, ...]:
    workflow_rows = db.execute(
        _lockable_statement(
            """
            SELECT
                job.id,
                job.organization_id,
                job.job_type,
                job.run_at,
                job.attempts,
                email_evidence.has_email_log,
                email_evidence.has_provider_id,
                email_evidence.has_sent_at
            FROM jobs AS job
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*) > 0 AS has_email_log,
                    COALESCE(
                        BOOL_OR(
                            NULLIF(to_jsonb(email_log)->>'external_id', '') IS NOT NULL
                        ),
                        FALSE
                    ) AS has_provider_id,
                    COALESCE(
                        BOOL_OR(NULLIF(to_jsonb(email_log)->>'sent_at', '') IS NOT NULL),
                        FALSE
                    ) AS has_sent_at
                    FROM email_logs AS email_log
                    WHERE email_log.organization_id = job.organization_id
                      AND (
                          email_log.job_id = job.id
                          OR (
                              to_jsonb(email_log)->>'source_type' = 'workflow_job'
                              AND to_jsonb(email_log)->>'source_id' = job.id::text
                          )
                      )
            ) AS email_evidence ON TRUE
            WHERE job.status = 'running'
              AND job.run_at < :stale_before
              AND job.claim_token IS NULL
              AND job.claimed_at IS NULL
              AND job.job_type = 'workflow_email'
            ORDER BY job.id
            """,
            lock=lock,
        ),
        {"stale_before": stale_before},
    ).mappings()
    decisions = [
        LegacyJobReconciliationDecision(
            job_id=row["id"],
            organization_id=row["organization_id"],
            job_type=row["job_type"],
            run_at=row["run_at"],
            attempts=row["attempts"],
            evidence_flags={
                "email_log_exists": row["has_email_log"],
                "email_log_has_provider_id": row["has_provider_id"],
                "email_log_has_sent_at": row["has_sent_at"],
            },
            target_status=JobStatus.FAILED.value,
            reason_code=(
                "workflow_email_outcome_unknown"
                if row["has_email_log"]
                else "workflow_email_no_local_delivery_evidence"
            ),
            non_replayable=True,
        )
        for row in workflow_rows
    ]

    attachment_rows = db.execute(
        _lockable_statement(
            """
            SELECT
                job.id,
                job.organization_id,
                job.job_type,
                job.run_at,
                job.attempts,
                attachment.quarantined
            FROM jobs AS job
            JOIN attachments AS attachment
              ON attachment.organization_id = job.organization_id
             AND attachment.id::text = job.payload->>'attachment_id'
            WHERE job.status = 'running'
              AND job.run_at < :stale_before
              AND job.claim_token IS NULL
              AND job.claimed_at IS NULL
              AND job.job_type = 'attachment_scan'
              AND attachment.scan_status = 'clean'
              AND attachment.scanned_at IS NOT NULL
            ORDER BY job.id
            """,
            lock=lock,
        ),
        {"stale_before": stale_before},
    ).mappings()
    decisions.extend(
        LegacyJobReconciliationDecision(
            job_id=row["id"],
            organization_id=row["organization_id"],
            job_type=row["job_type"],
            run_at=row["run_at"],
            attempts=row["attempts"],
            evidence_flags={
                "attachment_exists": True,
                "attachment_quarantined": row["quarantined"],
                "attachment_scan_clean": True,
                "attachment_scan_timestamp_present": True,
            },
            target_status=JobStatus.COMPLETED.value,
            reason_code="attachment_scan_already_clean",
            non_replayable=False,
        )
        for row in attachment_rows
    )

    periodic_sync_rows = db.execute(
        _lockable_statement(
            """
            SELECT job.id, job.organization_id, job.job_type, job.run_at, job.attempts
            FROM jobs AS job
            WHERE job.status = 'running'
              AND job.run_at < :stale_before
              AND job.claim_token IS NULL
              AND job.claimed_at IS NULL
              AND job.job_type IN ('google_calendar_sync', 'google_tasks_sync')
            ORDER BY job.id
            """,
            lock=lock,
        ),
        {"stale_before": stale_before},
    ).mappings()
    decisions.extend(
        LegacyJobReconciliationDecision(
            job_id=row["id"],
            organization_id=row["organization_id"],
            job_type=row["job_type"],
            run_at=row["run_at"],
            attempts=row["attempts"],
            evidence_flags={"recurring_sync_job": True},
            target_status=JobStatus.FAILED.value,
            reason_code="periodic_sync_superseded",
            non_replayable=True,
        )
        for row in periodic_sync_rows
    )

    organization_delete_rows = db.execute(
        _lockable_statement(
            """
            SELECT job.id, job.organization_id, job.job_type, job.run_at, job.attempts
            FROM jobs AS job
            JOIN organizations AS organization
              ON organization.id = job.organization_id
             AND organization.id::text = job.payload->>'org_id'
            WHERE job.status = 'running'
              AND job.run_at < :stale_before
              AND job.claim_token IS NULL
              AND job.claimed_at IS NULL
              AND job.job_type = 'org_delete'
              AND organization.deleted_at IS NOT NULL
              AND organization.purge_at IS NOT NULL
              AND organization.purge_at <= :evaluated_at
            ORDER BY job.id
            """,
            lock=lock,
        ),
        {
            "stale_before": stale_before,
            "evaluated_at": evaluated_at,
        },
    ).mappings()
    decisions.extend(
        LegacyJobReconciliationDecision(
            job_id=row["id"],
            organization_id=row["organization_id"],
            job_type=row["job_type"],
            run_at=row["run_at"],
            attempts=row["attempts"],
            evidence_flags={
                "organization_purge_due": True,
                "organization_soft_deleted": True,
            },
            target_status=JobStatus.FAILED.value,
            reason_code="organization_delete_requires_review",
            non_replayable=True,
        )
        for row in organization_delete_rows
    )
    return tuple(sorted(decisions, key=lambda decision: decision.job_id))


def reconcile_legacy_running_jobs(
    db: Session,
    *,
    stale_before: datetime,
    apply: bool,
    evaluated_at: datetime,
    expected_count: int | None = None,
    expected_fingerprint: str | None = None,
    review_reason: str | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> LegacyJobReconciliationReport:
    """Classify or atomically terminalize reviewed expired legacy jobs."""
    if apply and (expected_count is None or expected_fingerprint is None):
        raise ValueError("Apply requires expected_count and expected_fingerprint")
    normalized_review_reason = review_reason.strip() if review_reason is not None else ""
    if apply and not normalized_review_reason:
        raise ValueError("Apply requires a nonblank review_reason")
    if apply and len(normalized_review_reason) > 500:
        raise ValueError("review_reason must be 500 characters or fewer")

    apply_savepoint = db.begin_nested() if apply else None
    try:
        if apply:
            db.execute(
                text(
                    "SELECT pg_advisory_xact_lock("
                    "hashtextextended('surrogacyforce.legacy-job-reconciliation', 0)"
                    ")"
                )
            )
        ordered_decisions = _classify_legacy_running_jobs(
            db,
            stale_before=stale_before,
            evaluated_at=evaluated_at,
            lock=apply,
        )
        fingerprint = _fingerprint(
            ordered_decisions,
            stale_before=stale_before,
            evaluated_at=evaluated_at,
        )
        if apply and (
            len(ordered_decisions) != expected_count or fingerprint != expected_fingerprint
        ):
            raise ValueError("Legacy job reconciliation review no longer matches current jobs")

        applied_at = clock() if apply else None
        if apply:
            from app.services import audit_service

            assert applied_at is not None

            update_statement = text(
                """
                UPDATE jobs
                SET status = :target_status,
                    payload = jsonb_set(
                        COALESCE(payload, '{}'::jsonb),
                        '{_reconciliation}',
                        CAST(:marker AS jsonb),
                        true
                    ),
                    completed_at = CASE
                        WHEN :mark_completed THEN :applied_at
                        ELSE completed_at
                    END,
                    claim_token = NULL,
                    claimed_at = NULL
                WHERE id = :job_id
                  AND organization_id = :organization_id
                  AND job_type = :job_type
                  AND status = 'running'
                  AND run_at < :stale_before
                  AND claim_token IS NULL
                  AND claimed_at IS NULL
                """
            )
            for decision in ordered_decisions:
                marker = {
                    "schema_version": 1,
                    "non_replayable": decision.non_replayable,
                    "reason_code": decision.reason_code,
                    "evaluated_at": evaluated_at.isoformat(),
                    "applied_at": applied_at.isoformat(),
                    "fingerprint": fingerprint,
                }
                result = db.execute(
                    update_statement,
                    {
                        "target_status": decision.target_status,
                        "mark_completed": decision.target_status == JobStatus.COMPLETED.value,
                        "marker": json.dumps(marker, sort_keys=True, separators=(",", ":")),
                        "applied_at": applied_at,
                        "job_id": decision.job_id,
                        "organization_id": decision.organization_id,
                        "job_type": decision.job_type,
                        "stale_before": stale_before,
                    },
                )
                if (result.rowcount or 0) != 1:
                    raise RuntimeError("Legacy job changed while reconciliation was applying")
                audit_service.log_event(
                    db=db,
                    org_id=decision.organization_id,
                    event_type=AuditEventType.JOB_LEGACY_CLAIM_RECONCILED,
                    actor_user_id=None,
                    target_type="job",
                    target_id=decision.job_id,
                    details={
                        "schema_version": 1,
                        "target_status": decision.target_status,
                        "reason_code": decision.reason_code,
                        "non_replayable": decision.non_replayable,
                        "fingerprint": fingerprint,
                        "review_reason": normalized_review_reason,
                        "evaluated_at": evaluated_at.isoformat(),
                        "applied_at": applied_at.isoformat(),
                    },
                )
                db.flush()
            residual_count = _count_tokenless_running_jobs(db)
            if residual_count:
                raise ValueError(
                    f"Legacy job reconciliation blocked: {residual_count} "
                    "tokenless running jobs remain"
                )
            if apply_savepoint is not None:
                apply_savepoint.commit()
            db.commit()
        else:
            residual_count = _count_tokenless_running_jobs(db)
    except Exception:
        if apply:
            if apply_savepoint is not None and apply_savepoint.is_active:
                apply_savepoint.rollback()
            elif not db.is_active:
                db.rollback()
        raise

    return LegacyJobReconciliationReport(
        mode="apply" if apply else "dry_run",
        fingerprint=fingerprint,
        count=len(ordered_decisions),
        residual_count=residual_count,
        decisions=ordered_decisions,
        evaluated_at=evaluated_at,
        applied_at=applied_at,
    )
