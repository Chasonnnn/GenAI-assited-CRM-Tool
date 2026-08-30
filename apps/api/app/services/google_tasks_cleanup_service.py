"""Transactional tombstones for Google-synced task erasure."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import JobStatus, JobType, OwnerType
from app.db.models import Job, Membership, Task, User
from app.services import job_service

GOOGLE_DEFAULT_TASKLIST_ID = "@default"
MAX_GOOGLE_REMOTE_ID_LENGTH = 255


@dataclass(frozen=True, slots=True)
class GoogleTaskCleanupTarget:
    user_id: UUID
    google_task_id: str
    google_task_list_id: str


def _remote_id(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_GOOGLE_REMOTE_ID_LENGTH:
        raise ValueError(f"Google task cleanup requires a valid {field}")
    return value


def _idempotency_key(
    *,
    org_id: UUID,
    user_id: UUID,
    google_task_list_id: str,
    google_task_id: str,
) -> str:
    identity = f"{org_id}:{user_id}:{google_task_list_id}:{google_task_id}"
    digest = sha256(identity.encode("utf-8")).hexdigest()
    return f"google-task-remote-delete:{digest}"


def _enqueue_validated_remote_deletion(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    source_task_id: UUID,
    google_task_id: str,
    google_task_list_id: str,
) -> Job:
    google_task_id = _remote_id(google_task_id, field="google_task_id")
    google_task_list_id = _remote_id(
        google_task_list_id,
        field="google_task_list_id",
    )
    idempotency_key = _idempotency_key(
        org_id=org_id,
        user_id=user_id,
        google_task_list_id=google_task_list_id,
        google_task_id=google_task_id,
    )
    existing = db.query(Job).filter(Job.idempotency_key == idempotency_key).first()
    if existing is not None:
        if existing.organization_id != org_id:
            raise ValueError("Google task cleanup job is outside the organization")
        return existing

    # A legacy @default job can already have a concrete payload while retaining
    # its old idempotency key after colliding with another historical tombstone.
    existing_identity = (
        db.query(Job)
        .filter(
            Job.organization_id == org_id,
            Job.job_type == JobType.GOOGLE_TASK_REMOTE_DELETE.value,
            Job.payload["user_id"].astext == str(user_id),
            Job.payload["google_task_id"].astext == google_task_id,
            Job.payload["google_task_list_id"].astext == google_task_list_id,
        )
        .first()
    )
    if existing_identity is not None:
        return existing_identity

    if google_task_list_id != GOOGLE_DEFAULT_TASKLIST_ID:
        legacy_default_job = (
            db.query(Job)
            .filter(
                Job.organization_id == org_id,
                Job.job_type == JobType.GOOGLE_TASK_REMOTE_DELETE.value,
                Job.payload["user_id"].astext == str(user_id),
                Job.payload["google_task_id"].astext == google_task_id,
                Job.payload["google_task_list_id"].astext == GOOGLE_DEFAULT_TASKLIST_ID,
            )
            .with_for_update()
            .first()
        )
        if legacy_default_job is not None:
            legacy_default_job.payload = {
                **(legacy_default_job.payload or {}),
                "google_task_list_id": google_task_list_id,
            }
            legacy_default_job.idempotency_key = idempotency_key
            db.flush()
            return legacy_default_job

    payload = {
        "user_id": str(user_id),
        "source_task_id": str(source_task_id),
        "google_task_id": google_task_id,
        "google_task_list_id": google_task_list_id,
    }
    try:
        with db.begin_nested():
            return job_service.enqueue_job(
                db=db,
                org_id=org_id,
                job_type=JobType.GOOGLE_TASK_REMOTE_DELETE,
                payload=payload,
                idempotency_key=idempotency_key,
                commit=False,
            )
    except IntegrityError:
        return db.query(Job).filter(Job.idempotency_key == idempotency_key).one()


def enqueue_remote_deletion(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    source_task_id: UUID,
    google_task_id: str,
    google_task_list_id: str,
) -> Job:
    """Persist a remote-identity tombstone after validating organization membership."""
    membership = (
        db.query(Membership.id)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.organization_id == org_id,
            Membership.user_id == user_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .with_for_update(of=Membership)
        .first()
    )
    if membership is None:
        raise ValueError("Google task cleanup user is outside the organization")
    return _enqueue_validated_remote_deletion(
        db,
        org_id=org_id,
        user_id=user_id,
        source_task_id=source_task_id,
        google_task_id=google_task_id,
        google_task_list_id=google_task_list_id,
    )


def enqueue_donor_task_remote_deletions(
    db: Session,
    *,
    org_id: UUID,
    task_ids: set[UUID] | list[UUID],
) -> list[Job]:
    """Replace synced donor tasks with durable remote-delete jobs in this transaction."""
    requested_ids = set(task_ids)
    if not requested_ids:
        return []

    visible_task_ids = {
        task_id
        for (task_id,) in db.query(Task.id)
        .filter(
            Task.organization_id == org_id,
            Task.id.in_(requested_ids),
            Task.donor_id.is_not(None),
        )
        .all()
    }
    if visible_task_ids != requested_ids:
        raise ValueError("Google task cleanup target is outside the organization")

    # Lock memberships before tasks, matching sync/deprovision ordering. Taking
    # every active org membership is deliberate: the final task snapshot cannot
    # discover an owner whose membership was not already fenced.
    active_member_ids = {
        member_id
        for (member_id,) in db.query(Membership.user_id)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.organization_id == org_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .order_by(Membership.user_id)
        .with_for_update(of=Membership)
        .all()
    }
    tasks = (
        db.query(Task)
        .filter(
            Task.organization_id == org_id,
            Task.id.in_(requested_ids),
            Task.donor_id.is_not(None),
        )
        .order_by(Task.id)
        .with_for_update()
        .all()
    )
    if {task.id for task in tasks} != requested_ids:
        raise ValueError("Google task cleanup target changed during erasure")

    synced_tasks = [task for task in tasks if task.google_task_id]
    if not synced_tasks:
        return []

    owner_ids: set[UUID] = set()
    for task in synced_tasks:
        if task.owner_type != OwnerType.USER.value or task.owner_id is None:
            raise ValueError("Synced donor task has no organization user owner")
        owner_ids.add(task.owner_id)

    if not owner_ids.issubset(active_member_ids):
        raise ValueError("Synced donor task owner is outside the organization")

    jobs: list[Job] = []
    for task in synced_tasks:
        jobs.append(
            _enqueue_validated_remote_deletion(
                db,
                org_id=org_id,
                user_id=task.owner_id,
                source_task_id=task.id,
                google_task_id=task.google_task_id,
                google_task_list_id=(
                    task.google_task_list_id or GOOGLE_DEFAULT_TASKLIST_ID
                ),
            )
        )
    return jobs


def has_unresolved_cleanup_for_source_task(
    db: Session,
    *,
    org_id: UUID,
    source_task_id: UUID,
    user_id: UUID | None = None,
    exclude_job_id: UUID | None = None,
) -> bool:
    """Prevent another outbound POST while compensation is pending or failed."""
    query = db.query(Job.id).filter(
        Job.organization_id == org_id,
        Job.job_type == JobType.GOOGLE_TASK_REMOTE_DELETE.value,
        Job.status.in_(
            (
                JobStatus.PENDING.value,
                JobStatus.RUNNING.value,
                JobStatus.FAILED.value,
            )
        ),
        Job.payload["source_task_id"].astext == str(source_task_id),
    )
    if user_id is not None:
        query = query.filter(Job.payload["user_id"].astext == str(user_id))
    if exclude_job_id is not None:
        query = query.filter(Job.id != exclude_job_id)
    return query.first() is not None


def has_unresolved_prior_owner_work_for_source_task(
    db: Session,
    *,
    org_id: UUID,
    source_task_id: UUID,
    current_user_id: UUID,
) -> bool:
    """Fence a new owner until every prior remote identity is resolved."""
    if has_unresolved_cleanup_for_source_task(
        db,
        org_id=org_id,
        source_task_id=source_task_id,
    ):
        return True
    return (
        db.query(Job.id)
        .filter(
            Job.organization_id == org_id,
            Job.job_type == JobType.GOOGLE_TASK_CREATION_RECONCILE.value,
            Job.status.in_(
                (
                    JobStatus.PENDING.value,
                    JobStatus.RUNNING.value,
                    JobStatus.FAILED.value,
                )
            ),
            Job.payload["source_task_id"].astext == str(source_task_id),
            Job.payload["user_id"].astext != str(current_user_id),
        )
        .first()
        is not None
    )


def has_unresolved_google_task_work_for_user(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
) -> bool:
    """Return whether credentials are still required by a durable donor-task job."""
    return has_unresolved_google_task_work_for_user_in_organizations(
        db,
        org_ids={org_id},
        user_id=user_id,
    )


def has_unresolved_google_task_work_for_user_in_organizations(
    db: Session,
    *,
    org_ids: set[UUID] | None,
    user_id: UUID,
) -> bool:
    """Return whether any selected tenant still needs this user's credentials."""
    if org_ids == set():
        return False
    query = db.query(Job.id).filter(
        Job.job_type.in_(
            (
                JobType.GOOGLE_TASK_REMOTE_DELETE.value,
                JobType.GOOGLE_TASK_CREATION_RECONCILE.value,
            )
        ),
        Job.status.in_(
            (
                JobStatus.PENDING.value,
                JobStatus.RUNNING.value,
                JobStatus.FAILED.value,
            )
        ),
        Job.payload["user_id"].astext == str(user_id),
    )
    if org_ids is not None:
        query = query.filter(Job.organization_id.in_(org_ids))
    else:
        # UserIntegration is user-global, so disconnect must see durable work
        # outside the authenticated request's tenant backstop.
        query = query.execution_options(skip_org_scope=True)
    return query.first() is not None


def persist_concrete_cleanup_task_list_identity(
    db: Session,
    job: Job,
    *,
    target: GoogleTaskCleanupTarget,
    google_task_list_id: str,
) -> None:
    """Canonicalize a legacy @default tombstone without creating a duplicate."""
    concrete_task_list_id = _remote_id(
        google_task_list_id,
        field="google_task_list_id",
    )
    if concrete_task_list_id == target.google_task_list_id:
        return
    if job.organization_id is None:
        raise ValueError("Google task cleanup requires an organization-scoped job")

    canonical_key = _idempotency_key(
        org_id=job.organization_id,
        user_id=target.user_id,
        google_task_list_id=concrete_task_list_id,
        google_task_id=target.google_task_id,
    )
    duplicate = (
        db.query(Job.id)
        .filter(
            Job.id != job.id,
            Job.idempotency_key == canonical_key,
        )
        .with_for_update()
        .first()
    )
    job.payload = {
        **(job.payload or {}),
        "google_task_list_id": concrete_task_list_id,
    }
    if duplicate is None:
        job.idempotency_key = canonical_key


def reactivate_creation_recovery_after_cleanup(db: Session, job: Job) -> None:
    """Wake deferred new-owner sync after the last prior identity is erased."""
    if job.organization_id is None:
        return
    try:
        source_task_id = UUID(str((job.payload or {}).get("source_task_id")))
    except (TypeError, ValueError):
        return
    if has_unresolved_cleanup_for_source_task(
        db,
        org_id=job.organization_id,
        source_task_id=source_task_id,
        exclude_job_id=getattr(job, "id", None),
    ):
        return

    recovery_jobs = (
        db.query(Job)
        .filter(
            Job.organization_id == job.organization_id,
            Job.job_type == JobType.GOOGLE_TASK_CREATION_RECONCILE.value,
            Job.status.in_((JobStatus.PENDING.value, JobStatus.FAILED.value)),
            Job.payload["source_task_id"].astext == str(source_task_id),
        )
        .with_for_update()
        .all()
    )
    for recovery_job in recovery_jobs:
        recovery_job.status = JobStatus.PENDING.value
        recovery_job.run_at = datetime.now(UTC) + timedelta(seconds=5)
        recovery_job.attempts = 0
        recovery_job.completed_at = None
        recovery_job.last_error = None
        recovery_job.claim_token = None
        recovery_job.claimed_at = None


def validate_cleanup_job_target(db: Session, job: Job) -> GoogleTaskCleanupTarget:
    """Validate the durable job still belongs to the user's organization."""
    if job.organization_id is None:
        raise ValueError("Google task cleanup requires an organization-scoped job")

    payload = job.payload or {}
    try:
        user_id = UUID(str(payload.get("user_id")))
    except (TypeError, ValueError) as exc:
        raise ValueError("Google task cleanup requires a valid user_id") from exc

    membership = (
        db.query(Membership.id)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.organization_id == job.organization_id,
            Membership.user_id == user_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .with_for_update(of=Membership)
        .first()
    )
    if membership is None:
        raise ValueError("Google task cleanup user is outside the job organization")

    return GoogleTaskCleanupTarget(
        user_id=user_id,
        google_task_id=_remote_id(payload.get("google_task_id"), field="google_task_id"),
        google_task_list_id=_remote_id(
            payload.get("google_task_list_id"),
            field="google_task_list_id",
        ),
    )


def list_tombstoned_remote_keys(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
) -> set[tuple[str, str]]:
    """Return remote identities that inbound sync must never recreate."""
    payloads = (
        db.query(Job.payload)
        .filter(
            Job.organization_id == org_id,
            Job.job_type == JobType.GOOGLE_TASK_REMOTE_DELETE.value,
            Job.payload["user_id"].astext == str(user_id),
        )
        .all()
    )
    keys: set[tuple[str, str]] = set()
    for (payload,) in payloads:
        try:
            google_task_id = _remote_id(payload.get("google_task_id"), field="google_task_id")
            google_task_list_id = _remote_id(
                payload.get("google_task_list_id"),
                field="google_task_list_id",
            )
        except (AttributeError, ValueError):
            continue
        keys.add((google_task_list_id, google_task_id))
    return keys
