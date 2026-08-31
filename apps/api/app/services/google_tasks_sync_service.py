"""Google Tasks sync service for platform tasks."""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from urllib.parse import quote, unquote
from uuid import UUID

import httpx
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.async_utils import run_async
from app.db.enums import JobStatus, JobType, OwnerType, TaskType
from app.db.models import Donor, Job, Membership, Task, User
from app.services import oauth_service
from app.services.http_service import DEFAULT_RETRY_STATUSES, request_with_retries

logger = logging.getLogger(__name__)

GOOGLE_TASKS_API_BASE = "https://tasks.googleapis.com/tasks/v1"
GOOGLE_DEFAULT_TASKLIST_ID = "@default"
GOOGLE_TASKS_TIMEOUT_SECONDS = 30.0
GOOGLE_TASKS_RETRY_ATTEMPTS = 3
GOOGLE_TASKS_RETRY_BASE_DELAY = 0.5
GOOGLE_TASKS_RETRY_MAX_DELAY = 4.0
GOOGLE_TASKS_SCOPES = {
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/tasks.readonly",
}
GOOGLE_TASK_CORRELATION_LABEL = "Surrogacy Force task ID"
_GOOGLE_TASK_CORRELATION_RE = re.compile(
    rf"(?:^|\n)\[{re.escape(GOOGLE_TASK_CORRELATION_LABEL)}: "
    r"([0-9a-fA-F-]{36})\](?=\n|$)"
)


class _GoogleTasksInsufficientScopeError(Exception):
    """Signal an authenticated Google Tasks response that lacks Tasks scope."""


class _GoogleTasksReconciliationIncompleteError(Exception):
    """Signal that an uncertain donor POST cannot yet be reconciled safely."""


def _normalize_scopes(scopes: object) -> set[str]:
    if not isinstance(scopes, list):
        return set()
    return {str(scope).strip() for scope in scopes if str(scope).strip()}


def integration_has_google_tasks_scope(integration: object | None) -> bool:
    """Return whether a Google integration has tasks scope."""
    if integration is None:
        return False
    scopes = _normalize_scopes(getattr(integration, "granted_scopes", None))
    return bool(scopes.intersection(GOOGLE_TASKS_SCOPES))


def scopes_known_to_exclude_google_tasks(granted_scopes: object) -> bool:
    """
    Return True if scopes are explicitly known and exclude Google Tasks.

    If scopes are missing/null (legacy rows), returns False to preserve behavior.
    """
    if not isinstance(granted_scopes, list):
        return False
    scopes = _normalize_scopes(granted_scopes)
    if not scopes:
        return True
    return not bool(scopes.intersection(GOOGLE_TASKS_SCOPES))


def integration_scope_known_to_exclude_google_tasks(integration: object | None) -> bool:
    """
    Return True if scopes are explicitly known and exclude Google Tasks.

    If scopes are missing/null (legacy rows), returns False to preserve behavior.
    """
    if integration is None:
        return False
    raw_scopes = getattr(integration, "granted_scopes", None)
    return scopes_known_to_exclude_google_tasks(raw_scopes)


def _is_insufficient_scope_error(status_code: int, payload: dict[str, Any] | None) -> bool:
    if status_code != 403:
        return False
    if not payload or not isinstance(payload.get("error"), dict):
        return False
    error = payload["error"]
    message = error.get("message")
    if isinstance(message, str):
        lowered = message.lower()
        if (
            "insufficient authentication scopes" in lowered
            or "insufficientpermissions" in lowered
            or "insufficient permissions" in lowered
        ):
            return True

    errors = error.get("errors")
    if isinstance(errors, list):
        for item in errors:
            if not isinstance(item, dict):
                continue
            reason = str(item.get("reason") or "").lower()
            if reason in {"insufficientpermissions", "accesstokenscopeinsufficient"}:
                return True

    details = error.get("details")
    if isinstance(details, list):
        for item in details:
            if not isinstance(item, dict):
                continue
            reason = str(item.get("reason") or "").lower()
            if reason == "access_token_scope_insufficient":
                return True

    return False


def _mark_integration_missing_google_tasks_scope(integration: object) -> bool:
    """
    Persist explicit "no tasks scope" so schedulers can skip noisy retries.

    Returns True when granted_scopes changed.
    """
    current = getattr(integration, "granted_scopes", None)
    scopes = _normalize_scopes(current)
    filtered = sorted(scope for scope in scopes if scope not in GOOGLE_TASKS_SCOPES)
    if current == filtered:
        return False
    integration.granted_scopes = filtered
    return True


def _disable_google_tasks_after_scope_error(
    db: Session,
    *,
    integration: object,
    user_id: UUID,
) -> None:
    """Persist the scope failure once so later task mutations skip Google."""
    if not _mark_integration_missing_google_tasks_scope(integration):
        return
    db.commit()
    logger.warning(
        "Google Tasks outbound sync disabled (insufficient scopes) user=%s; reconnect Google Calendar integration",
        user_id,
    )


def _to_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_google_datetime(value: object | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return _to_utc(parsed)


def _to_google_datetime(value: datetime) -> str:
    utc_value = _to_utc(value) or datetime.now(UTC)
    return utc_value.isoformat().replace("+00:00", "Z")


def _encode_google_id(value: str) -> str:
    return quote(unquote(value), safe="")


def _task_due_to_google(task: Task) -> str | None:
    if not task.due_date:
        return None
    due_time = task.due_time or time.min
    due_dt = datetime.combine(task.due_date, due_time, tzinfo=UTC)
    return _to_google_datetime(due_dt)


def _google_due_to_task_fields(raw_due: object | None) -> tuple[date | None, time | None]:
    parsed = _parse_google_datetime(raw_due)
    if not parsed:
        return None, None
    parsed = _to_utc(parsed) or parsed
    parsed_time = parsed.time().replace(tzinfo=None, microsecond=0)
    if parsed_time == time.min:
        return parsed.date(), None
    return parsed.date(), parsed_time


def _build_google_task_payload(task: Task) -> dict[str, object]:
    notes = task.description or ""
    donor = task.donor if task.donor_id else None
    if donor and donor.organization_id == task.organization_id:
        donor_label = {"egg": "Egg donor", "sperm": "Sperm donor"}.get(
            donor.donor_type,
            "Donor",
        )
        subject_line = f"{donor_label} #{donor.donor_number}"
        notes = f"{notes}\n\n{subject_line}" if notes else subject_line
    if task.donor_id:
        correlation_marker = f"[{GOOGLE_TASK_CORRELATION_LABEL}: {task.id}]"
        notes = f"{notes}\n\n{correlation_marker}" if notes else correlation_marker

    payload: dict[str, object] = {
        "title": (task.title or "(No title)")[:255],
        "notes": notes,
        "status": "completed" if task.is_completed else "needsAction",
    }
    due_value = _task_due_to_google(task)
    if due_value:
        payload["due"] = due_value
    if task.is_completed and task.completed_at:
        payload["completed"] = _to_google_datetime(task.completed_at)
    return payload


def _google_task_correlation_id(notes: object | None) -> UUID | None:
    """Read our stable donor-task marker without trusting arbitrary remote notes."""
    if not isinstance(notes, str):
        return None
    match = _GOOGLE_TASK_CORRELATION_RE.search(notes)
    if match is None:
        return None
    try:
        return UUID(match.group(1))
    except ValueError:
        return None


def _strip_google_task_correlation_marker(notes: str | None) -> str | None:
    """Keep the internal reconciliation marker out of the local description."""
    if not notes:
        return notes
    cleaned = _GOOGLE_TASK_CORRELATION_RE.sub("", notes).strip()
    return cleaned or None


def _get_active_google_tasks_membership(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    lock: bool = False,
) -> Membership | None:
    """Resolve the exact active tenant membership used for provider authorization."""
    query = (
        db.query(Membership)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.organization_id == org_id,
            Membership.user_id == user_id,
            Membership.is_active.is_(True),
            User.is_active.is_(True),
        )
    )
    if lock:
        query = query.with_for_update(of=Membership)
    return query.one_or_none()


def require_active_google_tasks_membership(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    lock: bool = False,
) -> Membership:
    """Fail closed before any Google Tasks provider call for a stale job/user."""
    membership = _get_active_google_tasks_membership(
        db,
        org_id=org_id,
        user_id=user_id,
        lock=lock,
    )
    if membership is None:
        raise ValueError("Google Tasks user has no active membership in the job organization")
    return membership


async def _google_request(
    *,
    access_token: str,
    method: str,
    path: str,
    params: dict[str, str] | None = None,
    json_body: dict[str, object] | None = None,
    max_attempts: int = GOOGLE_TASKS_RETRY_ATTEMPTS,
) -> tuple[int, dict[str, Any] | None]:
    url = f"{GOOGLE_TASKS_API_BASE}{path}"
    try:
        async with httpx.AsyncClient(timeout=GOOGLE_TASKS_TIMEOUT_SECONDS) as client:

            async def request_fn() -> httpx.Response:
                return await client.request(
                    method,
                    url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    params=params,
                    json=json_body,
                )

            response = await request_with_retries(
                request_fn,
                max_attempts=max_attempts,
                base_delay=GOOGLE_TASKS_RETRY_BASE_DELAY,
                max_delay=GOOGLE_TASKS_RETRY_MAX_DELAY,
                retry_statuses=DEFAULT_RETRY_STATUSES,
            )
    except Exception as exc:
        logger.warning("Google Tasks request failed method=%s path=%s error=%s", method, path, exc)
        return 0, None

    payload: dict[str, Any] | None = None
    if response.content:
        try:
            decoded = response.json()
            if isinstance(decoded, dict):
                payload = decoded
        except Exception:
            payload = None

    if response.status_code >= 400:
        error_message = None
        if payload and isinstance(payload.get("error"), dict):
            raw_message = payload["error"].get("message")
            if isinstance(raw_message, str) and raw_message.strip():
                error_message = raw_message.strip()
        logger.warning(
            "Google Tasks API error method=%s path=%s status=%s message=%s",
            method,
            path,
            response.status_code,
            error_message or response.text[:300],
        )
    return response.status_code, payload


async def _resolve_concrete_google_task_list_id(
    access_token: str,
    task_list_id: str,
) -> str | None:
    """Resolve Google's @default alias to the durable list resource ID."""
    if task_list_id != GOOGLE_DEFAULT_TASKLIST_ID:
        return task_list_id
    encoded_task_list_id = _encode_google_id(GOOGLE_DEFAULT_TASKLIST_ID)
    status_code, payload = await _google_request(
        access_token=access_token,
        method="GET",
        path=f"/users/@me/lists/{encoded_task_list_id}",
    )
    if _is_insufficient_scope_error(status_code, payload):
        raise _GoogleTasksInsufficientScopeError
    if status_code != 200 or not payload:
        return None
    resolved = payload.get("id")
    if not isinstance(resolved, str) or not resolved or resolved == GOOGLE_DEFAULT_TASKLIST_ID:
        return None
    return resolved


async def _list_google_task_lists(
    access_token: str,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    results: list[dict[str, Any]] = []
    page_token: str | None = None

    while True:
        params = {"maxResults": "100"}
        if page_token:
            params["pageToken"] = page_token
        status_code, payload = await _google_request(
            access_token=access_token,
            method="GET",
            path="/users/@me/lists",
            params=params,
        )
        if status_code != 200:
            return results, {"status_code": status_code, "payload": payload}

        for item in payload.get("items", []) if payload else []:
            if isinstance(item, dict) and item.get("id"):
                results.append(item)

        page_token = payload.get("nextPageToken") if payload else None
        if not page_token:
            break

    if not results:
        default_id = await _resolve_concrete_google_task_list_id(
            access_token,
            GOOGLE_DEFAULT_TASKLIST_ID,
        )
        if default_id is None:
            return [], {"status_code": 0, "payload": None}
        return [{"id": default_id}], None
    return results, None


async def _list_google_tasks_snapshot(
    access_token: str,
    task_list_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Return a complete list snapshot or an explicit error for safe reconciliation."""
    results: list[dict[str, Any]] = []
    page_token: str | None = None
    encoded_task_list_id = _encode_google_id(task_list_id)

    while True:
        params = {
            "maxResults": "100",
            "showCompleted": "true",
            "showDeleted": "true",
            "showHidden": "true",
            "showAssigned": "true",
        }
        if page_token:
            params["pageToken"] = page_token

        status_code, payload = await _google_request(
            access_token=access_token,
            method="GET",
            path=f"/lists/{encoded_task_list_id}/tasks",
            params=params,
        )
        if status_code != 200:
            return results, {"status_code": status_code, "payload": payload}

        for item in payload.get("items", []) if payload else []:
            if isinstance(item, dict) and item.get("id"):
                results.append(item)

        page_token = payload.get("nextPageToken") if payload else None
        if not page_token:
            break

    return results, None


async def _list_google_tasks(access_token: str, task_list_id: str) -> list[dict[str, Any]]:
    results, _error = await _list_google_tasks_snapshot(access_token, task_list_id)
    return results


async def _find_correlated_google_donor_tasks(
    *,
    access_token: str,
    task_list_id: str,
    source_task_id: UUID,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Find every live remote task carrying one durable platform-task marker."""
    remote_tasks, error = await _list_google_tasks_snapshot(access_token, task_list_id)
    if error is not None:
        return [], error
    return (
        [
            remote_task
            for remote_task in remote_tasks
            if not remote_task.get("deleted")
            and _google_task_correlation_id(remote_task.get("notes")) == source_task_id
        ],
        None,
    )


def _remote_task_sort_key(remote_task: dict[str, Any]) -> tuple[datetime, str]:
    return (
        _parse_google_datetime(remote_task.get("updated")) or datetime.min.replace(tzinfo=UTC),
        str(remote_task.get("id") or ""),
    )


async def _reconcile_google_donor_task_creation(
    task: Task,
    db: Session,
    *,
    access_token: str,
    task_list_id: str,
) -> tuple[str, str, datetime | None] | None:
    """Recover a prior uncertain POST before another donor-task POST is allowed."""
    matches, error = await _find_correlated_google_donor_tasks(
        access_token=access_token,
        task_list_id=task_list_id,
        source_task_id=task.id,
    )
    if error is not None:
        status_code = int(error.get("status_code") or 0)
        payload = error.get("payload")
        if _is_insufficient_scope_error(status_code, payload):
            raise _GoogleTasksInsufficientScopeError
        raise _GoogleTasksReconciliationIncompleteError
    if not matches:
        return None

    matches.sort(key=_remote_task_sort_key, reverse=True)
    selected = matches[0]
    selected_id = selected.get("id")
    if not isinstance(selected_id, str) or not selected_id:
        return None

    # Older versions could retry an uncertain POST. Keep one deterministic
    # identity and durably erase every extra rather than leaving remote shadows.
    if len(matches) > 1:
        from app.services import google_tasks_cleanup_service

        for duplicate in matches[1:]:
            duplicate_id = duplicate.get("id")
            if not isinstance(duplicate_id, str) or not duplicate_id:
                continue
            google_tasks_cleanup_service.enqueue_remote_deletion(
                db,
                org_id=task.organization_id,
                user_id=task.owner_id,
                source_task_id=task.id,
                google_task_id=duplicate_id,
                google_task_list_id=task_list_id,
            )

    return selected_id, task_list_id, _parse_google_datetime(selected.get("updated"))


async def _upsert_google_task_for_platform_task(
    task: Task, db: Session
) -> tuple[str, str, datetime | None] | None:
    token = await oauth_service.get_access_token_async(db, task.owner_id, "google_calendar")
    if not token:
        return None

    task_list_id = await _resolve_concrete_google_task_list_id(
        token,
        task.google_task_list_id or GOOGLE_DEFAULT_TASKLIST_ID,
    )
    if task_list_id is None:
        return None
    encoded_task_list_id = _encode_google_id(task_list_id)
    payload = _build_google_task_payload(task)

    status_code = 0
    response_payload: dict[str, Any] | None = None
    attempted_creation = False
    if task.google_task_id:
        encoded_task_id = _encode_google_id(task.google_task_id)
        status_code, response_payload = await _google_request(
            access_token=token,
            method="PATCH",
            path=f"/lists/{encoded_task_list_id}/tasks/{encoded_task_id}",
            json_body=payload,
        )

    is_donor_task = task.donor_id is not None
    if is_donor_task and (not task.google_task_id or status_code == 404):
        reconciled = await _reconcile_google_donor_task_creation(
            task,
            db,
            access_token=token,
            task_list_id=task_list_id,
        )
        if reconciled is not None:
            return reconciled

    if not task.google_task_id or status_code == 404:
        attempted_creation = True
        status_code, response_payload = await _google_request(
            access_token=token,
            method="POST",
            path=f"/lists/{encoded_task_list_id}/tasks",
            json_body=payload,
            # A donor POST is never blindly replayed. Its durable marker and
            # recovery job reconcile the remote list before another attempt.
            max_attempts=1 if is_donor_task else GOOGLE_TASKS_RETRY_ATTEMPTS,
        )

    if _is_insufficient_scope_error(status_code, response_payload):
        raise _GoogleTasksInsufficientScopeError

    if status_code not in (200, 201) or not response_payload:
        if is_donor_task and attempted_creation:
            return await _reconcile_google_donor_task_creation(
                task,
                db,
                access_token=token,
                task_list_id=task_list_id,
            )
        return None

    remote_task_id = response_payload.get("id")
    if not remote_task_id or not isinstance(remote_task_id, str):
        if is_donor_task and attempted_creation:
            return await _reconcile_google_donor_task_creation(
                task,
                db,
                access_token=token,
                task_list_id=task_list_id,
            )
        return None

    remote_updated_at = _parse_google_datetime(response_payload.get("updated"))
    return remote_task_id, task_list_id, remote_updated_at


async def _delete_google_task_by_remote_identity(
    db: Session,
    *,
    user_id: UUID,
    google_task_list_id: str,
    google_task_id: str,
) -> bool:
    token = await oauth_service.get_access_token_async(db, user_id, "google_calendar")
    if not token:
        return False

    concrete_task_list_id = await _resolve_concrete_google_task_list_id(
        token,
        google_task_list_id,
    )
    if concrete_task_list_id is None:
        return False
    return await _delete_google_task_with_token(
        access_token=token,
        google_task_list_id=concrete_task_list_id,
        google_task_id=google_task_id,
    )


async def _delete_google_task_with_token(
    *,
    access_token: str,
    google_task_list_id: str,
    google_task_id: str,
) -> bool:
    encoded_task_list_id = _encode_google_id(google_task_list_id)
    encoded_task_id = _encode_google_id(google_task_id)
    status_code, response_payload = await _google_request(
        access_token=access_token,
        method="DELETE",
        path=f"/lists/{encoded_task_list_id}/tasks/{encoded_task_id}",
    )
    if _is_insufficient_scope_error(status_code, response_payload):
        raise _GoogleTasksInsufficientScopeError
    return status_code in (200, 204, 404)


async def _delete_google_task_for_platform_task(task: Task, db: Session) -> bool:
    if not task.google_task_id:
        return True
    return await _delete_google_task_by_remote_identity(
        db,
        user_id=task.owner_id,
        google_task_list_id=task.google_task_list_id or GOOGLE_DEFAULT_TASKLIST_ID,
        google_task_id=task.google_task_id,
    )


async def delete_google_task_for_cleanup(
    db: Session,
    *,
    user_id: UUID,
    google_task_list_id: str,
    google_task_id: str,
) -> str:
    """Delete a tombstoned remote task, raising so the worker can retry."""
    token = await oauth_service.get_access_token_async(db, user_id, "google_calendar")
    if not token:
        raise RuntimeError("Google Tasks access token is unavailable for cleanup")
    concrete_task_list_id = await _resolve_concrete_google_task_list_id(
        token,
        google_task_list_id,
    )
    if concrete_task_list_id is None:
        raise RuntimeError("Google task list could not be resolved for cleanup")
    deleted = await _delete_google_task_with_token(
        access_token=token,
        google_task_list_id=concrete_task_list_id,
        google_task_id=google_task_id,
    )
    if not deleted:
        raise RuntimeError("Google task remote deletion did not complete")
    return concrete_task_list_id


def _compensate_failed_donor_task_identity_persistence(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    source_task_id: UUID,
    google_task_list_id: str,
    google_task_id: str,
) -> None:
    """Tombstone then immediately delete a remote task whose ID was not persisted."""
    from app.services import google_tasks_cleanup_service

    try:
        google_tasks_cleanup_service.enqueue_remote_deletion(
            db,
            org_id=org_id,
            user_id=user_id,
            source_task_id=source_task_id,
            google_task_id=google_task_id,
            google_task_list_id=google_task_list_id,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(
            "Could not persist Google task compensation tombstone task=%s error=%s",
            source_task_id,
            exc,
        )

    try:
        deleted = run_async(
            _delete_google_task_by_remote_identity(
                db,
                user_id=user_id,
                google_task_list_id=google_task_list_id,
                google_task_id=google_task_id,
            ),
            timeout=30,
        )
    except Exception as exc:
        logger.warning(
            "Immediate Google task compensation failed task=%s error=%s",
            source_task_id,
            exc,
        )
        return
    if not deleted:
        logger.warning("Immediate Google task compensation deferred task=%s", source_task_id)


def _should_sync_task_to_google(task: Task) -> bool:
    return (
        task.owner_type == OwnerType.USER.value
        and task.task_type != TaskType.WORKFLOW_APPROVAL.value
    )


def _creation_recovery_idempotency_key(task: Task) -> str:
    return (
        f"google-task-create-reconcile:{task.organization_id}:{task.id}:{task.owner_id}"
    )


def _ensure_donor_creation_recovery_job(db: Session, task: Task) -> UUID:
    """Commit-before-POST outbox for every donor task provider mutation."""
    from app.services import job_service

    now = datetime.now(UTC)
    idempotency_key = _creation_recovery_idempotency_key(task)
    job = db.query(Job).filter(Job.idempotency_key == idempotency_key).one_or_none()
    payload = {
        "user_id": str(task.owner_id),
        "source_task_id": str(task.id),
        "google_task_list_id": task.google_task_list_id or GOOGLE_DEFAULT_TASKLIST_ID,
    }
    if job is None:
        job = job_service.enqueue_job(
            db=db,
            org_id=task.organization_id,
            job_type=JobType.GOOGLE_TASK_CREATION_RECONCILE,
            payload=payload,
            run_at=now + timedelta(minutes=2),
            idempotency_key=idempotency_key,
            commit=False,
        )
        job.max_attempts = 25
    else:
        if job.organization_id != task.organization_id:
            raise ValueError("Google task creation recovery job is outside the organization")
        if job.status == JobStatus.RUNNING.value:
            raise RuntimeError("Google task creation recovery is already running")
        job.payload = payload
        job.status = JobStatus.PENDING.value
        job.run_at = now + timedelta(minutes=2)
        job.attempts = 0
        job.completed_at = None
        job.last_error = None
        job.claim_token = None
        job.claimed_at = None
    db.commit()
    return job.id


def _complete_donor_creation_recovery_job(db: Session, recovery_job_id: UUID | None) -> None:
    if recovery_job_id is None:
        return
    job = (
        db.query(Job)
        .filter(
            Job.id == recovery_job_id,
            Job.job_type == JobType.GOOGLE_TASK_CREATION_RECONCILE.value,
        )
        .with_for_update()
        .one_or_none()
    )
    if job is None:
        raise RuntimeError("Google task creation recovery outbox disappeared")
    job.status = JobStatus.COMPLETED.value
    job.completed_at = datetime.now(UTC)
    job.last_error = None
    job.claim_token = None
    job.claimed_at = None


async def reconcile_uncertain_google_donor_task_creation(db: Session, job: Job) -> None:
    """Resolve one commit-before-POST outbox without ever blindly replaying a POST."""
    if job.organization_id is None:
        raise ValueError("Google task creation recovery requires an organization")
    payload = job.payload or {}
    try:
        user_id = UUID(str(payload.get("user_id")))
        source_task_id = UUID(str(payload.get("source_task_id")))
    except (TypeError, ValueError) as exc:
        raise ValueError("Google task creation recovery has invalid identifiers") from exc
    raw_task_list_id = payload.get("google_task_list_id")
    if not isinstance(raw_task_list_id, str) or not raw_task_list_id:
        raise ValueError("Google task creation recovery requires google_task_list_id")

    require_active_google_tasks_membership(
        db,
        org_id=job.organization_id,
        user_id=user_id,
        lock=True,
    )
    task = (
        db.query(Task)
        .filter(
            Task.organization_id == job.organization_id,
            Task.id == source_task_id,
            Task.donor_id.is_not(None),
        )
        .with_for_update()
        .one_or_none()
    )
    active_donor = None
    if task is not None:
        active_donor = (
            db.query(Donor.id)
            .filter(
                Donor.organization_id == job.organization_id,
                Donor.id == task.donor_id,
                Donor.is_archived.is_(False),
            )
            .one_or_none()
        )

    from app.services import google_tasks_cleanup_service, task_service

    can_keep_remote = (
        task is not None
        and active_donor is not None
        and task.owner_type == OwnerType.USER.value
        and task.owner_id == user_id
        and task_service.user_can_view_donors(db, job.organization_id, user_id)
    )
    if can_keep_remote and (
        google_tasks_cleanup_service.has_unresolved_prior_owner_work_for_source_task(
            db,
            org_id=job.organization_id,
            source_task_id=source_task_id,
            current_user_id=user_id,
        )
    ):
        raise RuntimeError("Prior-owner Google task resolution is not complete")

    integration = oauth_service.get_user_integration(db, user_id, "google_calendar")
    if not integration or integration_scope_known_to_exclude_google_tasks(integration):
        raise RuntimeError("Google Tasks credentials are unavailable for creation recovery")
    token = await oauth_service.get_access_token_async(db, user_id, "google_calendar")
    if not token:
        raise RuntimeError("Google Tasks access token is unavailable for creation recovery")
    task_list_id = await _resolve_concrete_google_task_list_id(token, raw_task_list_id)
    if task_list_id is None:
        raise RuntimeError("Google default task list could not be resolved")
    if task_list_id != raw_task_list_id:
        job.payload = {**payload, "google_task_list_id": task_list_id}

    if can_keep_remote and task is not None:
        if task.google_task_id:
            concrete_existing_list = await _resolve_concrete_google_task_list_id(
                token,
                task.google_task_list_id or GOOGLE_DEFAULT_TASKLIST_ID,
            )
            if concrete_existing_list is None:
                raise RuntimeError("Google task list identity could not be resolved")
            reconciled = await _reconcile_google_donor_task_creation(
                task,
                db,
                access_token=token,
                task_list_id=concrete_existing_list,
            )
            if reconciled is not None:
                remote_task_id, resolved_list_id, remote_updated_at = reconciled
                task.google_task_id = remote_task_id
                task.google_task_list_id = resolved_list_id
                task.google_task_updated_at = remote_updated_at
            else:
                task.google_task_list_id = concrete_existing_list
            db.flush()
            return

        result = await _upsert_google_task_for_platform_task(task, db)
        if result is None:
            raise RuntimeError("Google donor task creation remains unreconciled")
        remote_task_id, resolved_list_id, remote_updated_at = result
        task.google_task_id = remote_task_id
        task.google_task_list_id = resolved_list_id
        task.google_task_updated_at = remote_updated_at
        job.payload = {**job.payload, "google_task_list_id": resolved_list_id}
        db.flush()
        return

    # The source disappeared, was archived/reassigned, or the owner lost donor
    # access. Reconcile the marker and erase every matching remote task.
    matches, error = await _find_correlated_google_donor_tasks(
        access_token=token,
        task_list_id=task_list_id,
        source_task_id=source_task_id,
    )
    if error is not None:
        raise RuntimeError("Google donor task deletion reconciliation is incomplete")
    remote_ids = {
        remote_id
        for remote_task in matches
        if isinstance((remote_id := remote_task.get("id")), str) and remote_id
    }
    if task is not None and task.owner_id == user_id and task.google_task_id:
        remote_ids.add(task.google_task_id)
    for remote_id in sorted(remote_ids):
        deleted = await _delete_google_task_by_remote_identity(
            db,
            user_id=user_id,
            google_task_list_id=task_list_id,
            google_task_id=remote_id,
        )
        if not deleted:
            raise RuntimeError("Google donor task recovery deletion did not complete")
    if task is not None and task.owner_id == user_id:
        task.google_task_id = None
        task.google_task_list_id = None
        task.google_task_updated_at = None
    # A reassignment can happen while the prior owner's POST outcome is still
    # uncertain. Wake the new owner's outbox after this marker is resolved.
    google_tasks_cleanup_service.reactivate_creation_recovery_after_cleanup(db, job)
    db.flush()


def sync_platform_task_to_google(db: Session, task: Task) -> None:
    """Best-effort outbound sync from platform task to Google Tasks."""
    requested_task_id = task.id
    fenced_donor_sync = task.donor_id is not None
    recovery_job_id: UUID | None = None
    if fenced_donor_sync:
        try:
            require_active_google_tasks_membership(
                db,
                org_id=task.organization_id,
                user_id=task.owner_id,
                lock=True,
            )
        except ValueError:
            db.commit()
            return
        locked_task = (
            db.query(Task)
            .filter(
                Task.organization_id == task.organization_id,
                Task.id == task.id,
            )
            .with_for_update()
            .one_or_none()
        )
        if locked_task is None or locked_task.donor_id is None:
            db.commit()
            return
        task = locked_task
        active_donor = (
            db.query(Donor.id)
            .filter(
                Donor.organization_id == task.organization_id,
                Donor.id == task.donor_id,
                Donor.is_archived.is_(False),
            )
            .one_or_none()
        )
        if active_donor is None:
            db.commit()
            return

    if not _should_sync_task_to_google(task):
        if fenced_donor_sync:
            db.commit()
        return
    if fenced_donor_sync:
        from app.services import google_tasks_cleanup_service, task_service

        if not task_service.user_can_view_donors(
            db,
            task.organization_id,
            task.owner_id,
        ):
            db.commit()
            return
    integration = oauth_service.get_user_integration(db, task.owner_id, "google_calendar")
    if not integration:
        if fenced_donor_sync:
            db.commit()
        return
    if integration_scope_known_to_exclude_google_tasks(integration):
        if fenced_donor_sync:
            db.commit()
        return

    if fenced_donor_sync and (
        google_tasks_cleanup_service.has_unresolved_prior_owner_work_for_source_task(
            db,
            org_id=task.organization_id,
            source_task_id=task.id,
            current_user_id=task.owner_id,
        )
    ):
        try:
            _ensure_donor_creation_recovery_job(db, task)
        except Exception as exc:
            db.rollback()
            logger.warning(
                "Could not defer Google donor task sync behind prior-owner cleanup task=%s error=%s",
                requested_task_id,
                exc,
            )
        return

    if fenced_donor_sync:
        try:
            recovery_job_id = _ensure_donor_creation_recovery_job(db, task)
            # The outbox commit releases the provider-call fence. Reacquire the
            # exact member and task locks before any Google request.
            require_active_google_tasks_membership(
                db,
                org_id=task.organization_id,
                user_id=task.owner_id,
                lock=True,
            )
            task = (
                db.query(Task)
                .filter(
                    Task.organization_id == task.organization_id,
                    Task.id == task.id,
                    Task.donor_id.is_not(None),
                )
                .with_for_update()
                .one_or_none()
            )
            if task is None:
                db.commit()
                return
            active_donor = (
                db.query(Donor.id)
                .filter(
                    Donor.organization_id == task.organization_id,
                    Donor.id == task.donor_id,
                    Donor.is_archived.is_(False),
                )
                .one_or_none()
            )
            if active_donor is None:
                db.commit()
                return
            if google_tasks_cleanup_service.has_unresolved_prior_owner_work_for_source_task(
                db,
                org_id=task.organization_id,
                source_task_id=task.id,
                current_user_id=task.owner_id,
            ):
                db.commit()
                return
            integration = oauth_service.get_user_integration(
                db,
                task.owner_id,
                "google_calendar",
            )
            if not integration or integration_scope_known_to_exclude_google_tasks(integration):
                db.commit()
                return
        except Exception as exc:
            db.rollback()
            logger.warning(
                "Could not persist or reacquire Google donor-task recovery fence task=%s error=%s",
                requested_task_id,
                exc,
            )
            return

    source_task_id = task.id
    source_org_id = task.organization_id
    source_owner_id = task.owner_id
    original_google_task_id = task.google_task_id
    try:
        result = run_async(_upsert_google_task_for_platform_task(task, db), timeout=30)
    except _GoogleTasksInsufficientScopeError:
        _disable_google_tasks_after_scope_error(
            db,
            integration=integration,
            user_id=task.owner_id,
        )
        if fenced_donor_sync and db.in_transaction():
            db.commit()
        return
    except Exception as exc:
        if fenced_donor_sync:
            db.commit()
        logger.warning("Platform→Google task sync failed task=%s error=%s", task.id, exc)
        return

    if not result:
        if fenced_donor_sync:
            db.commit()
        return

    remote_task_id, task_list_id, remote_updated_at = result
    changed = False
    if task.google_task_id != remote_task_id:
        task.google_task_id = remote_task_id
        changed = True
    if task.google_task_list_id != task_list_id:
        task.google_task_list_id = task_list_id
        changed = True
    if remote_updated_at and task.google_task_updated_at != remote_updated_at:
        task.google_task_updated_at = remote_updated_at
        changed = True

    if changed or fenced_donor_sync:
        try:
            _complete_donor_creation_recovery_job(db, recovery_job_id)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(
                "Platform→Google task identity persistence failed task=%s error=%s",
                source_task_id,
                exc,
            )
            if fenced_donor_sync and original_google_task_id is None:
                _compensate_failed_donor_task_identity_persistence(
                    db,
                    org_id=source_org_id,
                    user_id=source_owner_id,
                    source_task_id=source_task_id,
                    google_task_list_id=task_list_id,
                    google_task_id=remote_task_id,
                )


def delete_platform_task_from_google(db: Session, task: Task) -> None:
    """Best-effort delete from Google Tasks when local task is deleted."""
    if not _should_sync_task_to_google(task) or not task.google_task_id:
        return

    integration = oauth_service.get_user_integration(db, task.owner_id, "google_calendar")
    if not integration:
        return
    if integration_scope_known_to_exclude_google_tasks(integration):
        return

    try:
        run_async(_delete_google_task_for_platform_task(task, db), timeout=30)
    except _GoogleTasksInsufficientScopeError:
        _disable_google_tasks_after_scope_error(
            db,
            integration=integration,
            user_id=task.owner_id,
        )
    except Exception as exc:
        logger.warning("Platform delete→Google task sync failed task=%s error=%s", task.id, exc)


def _is_google_task_newer(local: Task, remote_updated_at: datetime | None) -> bool:
    local_updated = _to_utc(local.google_task_updated_at)
    if remote_updated_at is None:
        return local_updated is None
    if local_updated is None:
        return True
    return remote_updated_at > local_updated


def _task_can_be_deleted_from_google_signal(task: Task) -> bool:
    return (
        task.task_type == TaskType.OTHER.value
        and task.surrogate_id is None
        and task.intended_parent_id is None
        and task.donor_id is None
        and task.workflow_execution_id is None
    )


async def _sync_google_tasks_for_user_async(db: Session, *, user_id: UUID, org_id: UUID) -> int:
    require_active_google_tasks_membership(
        db,
        org_id=org_id,
        user_id=user_id,
        lock=True,
    )
    integration = oauth_service.get_user_integration(db, user_id, "google_calendar")
    if not integration:
        return 0
    if integration_scope_known_to_exclude_google_tasks(integration):
        logger.info(
            "Skipping Google Tasks sync due to missing tasks scope user=%s org=%s",
            user_id,
            org_id,
        )
        return 0

    token = await oauth_service.get_access_token_async(db, user_id, "google_calendar")
    if not token:
        return 0

    task_lists, list_error = await _list_google_task_lists(token)
    if list_error:
        status_code = int(list_error.get("status_code") or 0)
        payload = list_error.get("payload")
        if _is_insufficient_scope_error(status_code, payload):
            if _mark_integration_missing_google_tasks_scope(integration):
                db.commit()
            logger.warning(
                "Google Tasks sync disabled (insufficient scopes) user=%s org=%s; reconnect Google Calendar integration",
                user_id,
                org_id,
            )
        return 0
    if not task_lists:
        return 0

    existing_tasks = (
        db.query(Task)
        .filter(
            Task.organization_id == org_id,
            Task.owner_type == OwnerType.USER.value,
            Task.owner_id == user_id,
            Task.google_task_id.is_not(None),
        )
        .all()
    )
    from app.services import google_tasks_cleanup_service, task_service

    blocked_google_task_keys = google_tasks_cleanup_service.list_tombstoned_remote_keys(
        db,
        org_id=org_id,
        user_id=user_id,
    )
    can_view_donors = task_service.user_can_view_donors(db, org_id, user_id)
    if not can_view_donors:
        blocked_google_task_keys.update(
            (
                task.google_task_list_id or GOOGLE_DEFAULT_TASKLIST_ID,
                task.google_task_id,
            )
            for task in existing_tasks
            if task.donor_id and task.google_task_id
        )
        existing_tasks = [task for task in existing_tasks if not task.donor_id]
    blocked_default_list_task_ids = {
        google_task_id
        for google_task_list_id, google_task_id in blocked_google_task_keys
        if google_task_list_id == GOOGLE_DEFAULT_TASKLIST_ID
    }
    needs_default_alias_resolution = bool(blocked_default_list_task_ids) or any(
        task.google_task_list_id in (None, GOOGLE_DEFAULT_TASKLIST_ID)
        for task in existing_tasks
    )
    concrete_default_task_list_id: str | None = None
    if needs_default_alias_resolution:
        if len(task_lists) == 1 and isinstance(task_lists[0].get("id"), str):
            concrete_default_task_list_id = task_lists[0]["id"]
        else:
            concrete_default_task_list_id = await _resolve_concrete_google_task_list_id(
                token,
                GOOGLE_DEFAULT_TASKLIST_ID,
            )

    def canonical_task_list_id(task_list_id: str | None) -> str:
        resolved = task_list_id or GOOGLE_DEFAULT_TASKLIST_ID
        if (
            resolved == GOOGLE_DEFAULT_TASKLIST_ID
            and concrete_default_task_list_id is not None
        ):
            return concrete_default_task_list_id
        return resolved

    existing_by_key: dict[tuple[str, str], Task] = {}
    changed_count = 0
    for local_task in existing_tasks:
        if local_task.google_task_id:
            canonical_key = (
                canonical_task_list_id(local_task.google_task_list_id),
                local_task.google_task_id,
            )
            incumbent = existing_by_key.get(canonical_key)
            if incumbent is not None and incumbent.id != local_task.id:
                incumbent_priority = (
                    incumbent.donor_id is not None,
                    incumbent.google_task_list_id
                    not in (None, GOOGLE_DEFAULT_TASKLIST_ID),
                    str(incumbent.id),
                )
                candidate_priority = (
                    local_task.donor_id is not None,
                    local_task.google_task_list_id
                    not in (None, GOOGLE_DEFAULT_TASKLIST_ID),
                    str(local_task.id),
                )
                winner, duplicate = (
                    (local_task, incumbent)
                    if candidate_priority > incumbent_priority
                    else (incumbent, local_task)
                )
                existing_by_key[canonical_key] = winner
                if _task_can_be_deleted_from_google_signal(duplicate):
                    db.delete(duplicate)
                else:
                    duplicate.google_task_id = None
                    duplicate.google_task_list_id = None
                    duplicate.google_task_updated_at = None
                changed_count += 1
            else:
                existing_by_key[canonical_key] = local_task

    legacy_default_by_remote_id = {
        local_task.google_task_id: local_task
        for local_task in existing_by_key.values()
        if local_task.google_task_id
        and local_task.google_task_list_id in (None, GOOGLE_DEFAULT_TASKLIST_ID)
    }

    for task_list in task_lists:
        task_list_id_raw = task_list.get("id")
        if not task_list_id_raw or not isinstance(task_list_id_raw, str):
            continue
        task_list_id = task_list_id_raw
        google_tasks = await _list_google_tasks(token, task_list_id)

        for google_task in google_tasks:
            google_task_id_raw = google_task.get("id")
            if not google_task_id_raw or not isinstance(google_task_id_raw, str):
                continue
            google_task_id = google_task_id_raw
            google_task_key = (task_list_id, google_task_id)
            if (
                google_task_key in blocked_google_task_keys
                or google_task_id in blocked_default_list_task_ids
            ):
                continue
            local = existing_by_key.get(google_task_key)
            if local is None:
                local = legacy_default_by_remote_id.get(google_task_id)

            correlation_id = _google_task_correlation_id(google_task.get("notes"))
            if correlation_id is not None:
                if not can_view_donors:
                    continue
                correlated_local = (
                    db.query(Task)
                    .join(
                        Donor,
                        and_(
                            Donor.id == Task.donor_id,
                            Donor.organization_id == Task.organization_id,
                        ),
                    )
                    .filter(
                        Task.organization_id == org_id,
                        Task.id == correlation_id,
                        Task.owner_type == OwnerType.USER.value,
                        Task.owner_id == user_id,
                        Task.donor_id.is_not(None),
                        Donor.is_archived.is_(False),
                    )
                    .with_for_update(of=Task)
                    .one_or_none()
                )
                # A branded marker without its exact active tenant-owned source
                # is stale donor data, never a generic task to import.
                if correlated_local is None:
                    continue
                local = correlated_local
                if (
                    local.google_task_id
                    and (
                        canonical_task_list_id(local.google_task_list_id),
                        local.google_task_id,
                    )
                    != google_task_key
                ):
                    # Preserve the persisted identity and tombstone the marked
                    # shadow instead of oscillating between duplicate remotes.
                    google_tasks_cleanup_service.enqueue_remote_deletion(
                        db,
                        org_id=org_id,
                        user_id=user_id,
                        source_task_id=local.id,
                        google_task_id=google_task_id,
                        google_task_list_id=task_list_id,
                    )
                    continue

            is_deleted = bool(google_task.get("deleted"))
            if is_deleted:
                if local:
                    if _task_can_be_deleted_from_google_signal(local):
                        db.delete(local)
                    else:
                        local.google_task_id = None
                        local.google_task_list_id = None
                        local.google_task_updated_at = None
                    changed_count += 1
                continue

            title_raw = google_task.get("title")
            title = (
                title_raw.strip()
                if isinstance(title_raw, str) and title_raw.strip()
                else "(No title)"
            )
            notes_raw = google_task.get("notes")
            notes = notes_raw if isinstance(notes_raw, str) and notes_raw else None
            if correlation_id is not None:
                notes = _strip_google_task_correlation_marker(notes)
            due_date_value, due_time_value = _google_due_to_task_fields(google_task.get("due"))
            is_completed = str(google_task.get("status") or "").lower() == "completed"
            completed_at = (
                _parse_google_datetime(google_task.get("completed")) if is_completed else None
            )
            remote_updated_at = _parse_google_datetime(google_task.get("updated"))

            if local:
                identity_changed = False
                if local.google_task_list_id != task_list_id:
                    local.google_task_list_id = task_list_id
                    identity_changed = True
                if local.google_task_id != google_task_id:
                    local.google_task_id = google_task_id
                    identity_changed = True
                if not _is_google_task_newer(local, remote_updated_at):
                    if identity_changed:
                        changed_count += 1
                    existing_by_key[google_task_key] = local
                    continue

                changed = identity_changed
                if local.title != title:
                    local.title = title
                    changed = True
                if local.description != notes:
                    local.description = notes
                    changed = True
                if local.due_date != due_date_value:
                    local.due_date = due_date_value
                    changed = True
                if local.due_time != due_time_value:
                    local.due_time = due_time_value
                    changed = True
                if local.is_completed != is_completed:
                    local.is_completed = is_completed
                    changed = True
                if local.completed_at != completed_at:
                    local.completed_at = completed_at
                    changed = True

                completed_by = user_id if is_completed else None
                if local.completed_by_user_id != completed_by:
                    local.completed_by_user_id = completed_by
                    changed = True

                normalized_remote_updated_at = _to_utc(remote_updated_at)
                if (
                    normalized_remote_updated_at
                    and local.google_task_updated_at != normalized_remote_updated_at
                ):
                    local.google_task_updated_at = normalized_remote_updated_at
                    changed = True

                if changed:
                    changed_count += 1
                existing_by_key[google_task_key] = local
                continue

            new_task = Task(
                organization_id=org_id,
                created_by_user_id=user_id,
                owner_type=OwnerType.USER.value,
                owner_id=user_id,
                title=title,
                description=notes,
                task_type=TaskType.OTHER.value,
                due_date=due_date_value,
                due_time=due_time_value,
                is_completed=is_completed,
                completed_at=completed_at,
                completed_by_user_id=user_id if is_completed else None,
                google_task_id=google_task_id,
                google_task_list_id=task_list_id,
                google_task_updated_at=remote_updated_at,
            )
            db.add(new_task)
            existing_by_key[(task_list_id, google_task_id)] = new_task
            changed_count += 1

    if changed_count:
        db.flush()
    return changed_count


def sync_google_tasks_for_user(db: Session, *, user_id: UUID, org_id: UUID) -> int:
    """Best-effort inbound sync from Google Tasks to platform tasks."""
    integration = oauth_service.get_user_integration(db, user_id, "google_calendar")
    if not integration:
        return 0
    if integration_scope_known_to_exclude_google_tasks(integration):
        return 0

    coro = _sync_google_tasks_for_user_async(db, user_id=user_id, org_id=org_id)
    try:
        return run_async(coro, timeout=45)
    except Exception as exc:
        try:
            coro.close()
        except Exception:
            pass
        logger.warning(
            "Google→Platform task sync failed user=%s org=%s error=%s", user_id, org_id, exc
        )
        return 0


async def sync_google_tasks_for_user_async(db: Session, *, user_id: UUID, org_id: UUID) -> int:
    """Async-safe inbound sync from Google Tasks to platform tasks."""
    integration = oauth_service.get_user_integration(db, user_id, "google_calendar")
    if not integration:
        return 0
    if integration_scope_known_to_exclude_google_tasks(integration):
        return 0

    try:
        return await _sync_google_tasks_for_user_async(db, user_id=user_id, org_id=org_id)
    except Exception as exc:
        logger.warning(
            "Google→Platform task async sync failed user=%s org=%s error=%s",
            user_id,
            org_id,
            exc,
        )
        return 0


async def _check_google_tasks_access_async(db: Session, user_id: UUID) -> tuple[bool, str | None]:
    token = await oauth_service.get_access_token_async(db, user_id, "google_calendar")
    if not token:
        return False, "missing_access_token"

    status_code, payload = await _google_request(
        access_token=token,
        method="GET",
        path="/users/@me/lists",
        params={"maxResults": "1"},
    )
    if status_code == 200:
        return True, None

    if payload and isinstance(payload.get("error"), dict):
        raw_message = payload["error"].get("message")
        if isinstance(raw_message, str) and raw_message.strip():
            return False, raw_message.strip()
    if status_code == 0:
        return False, "request_failed"
    return False, f"http_{status_code}"


def check_google_tasks_access(db: Session, user_id: UUID) -> tuple[bool, str | None]:
    """Verify whether a connected user can access Google Tasks API."""
    integration = oauth_service.get_user_integration(db, user_id, "google_calendar")
    if not integration:
        return False, "not_connected"

    try:
        return run_async(_check_google_tasks_access_async(db, user_id), timeout=20)
    except Exception as exc:
        logger.warning("Google Tasks access probe failed user=%s error=%s", user_id, exc)
        return False, "probe_failed"
