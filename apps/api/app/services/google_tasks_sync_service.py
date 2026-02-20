"""Google Tasks sync service for platform tasks."""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
from typing import Any
from urllib.parse import quote, unquote
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.async_utils import run_async
from app.db.enums import OwnerType, TaskType
from app.db.models import Task
from app.services import oauth_service

logger = logging.getLogger(__name__)

GOOGLE_TASKS_API_BASE = "https://tasks.googleapis.com/tasks/v1"
GOOGLE_DEFAULT_TASKLIST_ID = "@default"


def _to_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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
    utc_value = _to_utc(value) or datetime.now(timezone.utc)
    return utc_value.isoformat().replace("+00:00", "Z")


def _encode_google_id(value: str) -> str:
    return quote(unquote(value), safe="")


def _task_due_to_google(task: Task) -> str | None:
    if not task.due_date:
        return None
    due_time = task.due_time or time.min
    due_dt = datetime.combine(task.due_date, due_time, tzinfo=timezone.utc)
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
    payload: dict[str, object] = {
        "title": (task.title or "(No title)")[:255],
        "notes": task.description or "",
        "status": "completed" if task.is_completed else "needsAction",
    }
    due_value = _task_due_to_google(task)
    if due_value:
        payload["due"] = due_value
    if task.is_completed and task.completed_at:
        payload["completed"] = _to_google_datetime(task.completed_at)
    return payload


async def _google_request(
    *,
    access_token: str,
    method: str,
    path: str,
    params: dict[str, str] | None = None,
    json_body: dict[str, object] | None = None,
) -> tuple[int, dict[str, Any] | None]:
    url = f"{GOOGLE_TASKS_API_BASE}{path}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
                json=json_body,
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


async def _list_google_task_lists(access_token: str) -> list[dict[str, Any]]:
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
            return results

        for item in payload.get("items", []) if payload else []:
            if isinstance(item, dict) and item.get("id"):
                results.append(item)

        page_token = payload.get("nextPageToken") if payload else None
        if not page_token:
            break

    if not results:
        return [{"id": GOOGLE_DEFAULT_TASKLIST_ID}]
    return results


async def _list_google_tasks(access_token: str, task_list_id: str) -> list[dict[str, Any]]:
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
            return results

        for item in payload.get("items", []) if payload else []:
            if isinstance(item, dict) and item.get("id"):
                results.append(item)

        page_token = payload.get("nextPageToken") if payload else None
        if not page_token:
            break

    return results


async def _upsert_google_task_for_platform_task(
    task: Task, db: Session
) -> tuple[str, str, datetime | None] | None:
    token = await oauth_service.get_access_token_async(db, task.owner_id, "google_calendar")
    if not token:
        return None

    task_list_id = task.google_task_list_id or GOOGLE_DEFAULT_TASKLIST_ID
    encoded_task_list_id = _encode_google_id(task_list_id)
    payload = _build_google_task_payload(task)

    status_code = 0
    response_payload: dict[str, Any] | None = None
    if task.google_task_id:
        encoded_task_id = _encode_google_id(task.google_task_id)
        status_code, response_payload = await _google_request(
            access_token=token,
            method="PATCH",
            path=f"/lists/{encoded_task_list_id}/tasks/{encoded_task_id}",
            json_body=payload,
        )

    if not task.google_task_id or status_code == 404:
        status_code, response_payload = await _google_request(
            access_token=token,
            method="POST",
            path=f"/lists/{encoded_task_list_id}/tasks",
            json_body=payload,
        )

    if status_code not in (200, 201) or not response_payload:
        return None

    remote_task_id = response_payload.get("id")
    if not remote_task_id or not isinstance(remote_task_id, str):
        return None

    remote_updated_at = _parse_google_datetime(response_payload.get("updated"))
    return remote_task_id, task_list_id, remote_updated_at


async def _delete_google_task_for_platform_task(task: Task, db: Session) -> bool:
    if not task.google_task_id:
        return True

    token = await oauth_service.get_access_token_async(db, task.owner_id, "google_calendar")
    if not token:
        return False

    task_list_id = task.google_task_list_id or GOOGLE_DEFAULT_TASKLIST_ID
    encoded_task_list_id = _encode_google_id(task_list_id)
    encoded_task_id = _encode_google_id(task.google_task_id)
    status_code, _ = await _google_request(
        access_token=token,
        method="DELETE",
        path=f"/lists/{encoded_task_list_id}/tasks/{encoded_task_id}",
    )
    return status_code in (200, 204, 404)


def _should_sync_task_to_google(task: Task) -> bool:
    return (
        task.owner_type == OwnerType.USER.value
        and task.task_type != TaskType.WORKFLOW_APPROVAL.value
    )


def sync_platform_task_to_google(db: Session, task: Task) -> None:
    """Best-effort outbound sync from platform task to Google Tasks."""
    if not _should_sync_task_to_google(task):
        return

    integration = oauth_service.get_user_integration(db, task.owner_id, "google_calendar")
    if not integration:
        return

    try:
        result = run_async(_upsert_google_task_for_platform_task(task, db), timeout=30)
    except Exception as exc:
        logger.warning("Platform→Google task sync failed task=%s error=%s", task.id, exc)
        return

    if not result:
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

    if changed:
        db.commit()


def delete_platform_task_from_google(db: Session, task: Task) -> None:
    """Best-effort delete from Google Tasks when local task is deleted."""
    if not _should_sync_task_to_google(task) or not task.google_task_id:
        return

    integration = oauth_service.get_user_integration(db, task.owner_id, "google_calendar")
    if not integration:
        return

    try:
        run_async(_delete_google_task_for_platform_task(task, db), timeout=30)
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
        and task.workflow_execution_id is None
    )


async def _sync_google_tasks_for_user_async(db: Session, *, user_id: UUID, org_id: UUID) -> int:
    token = await oauth_service.get_access_token_async(db, user_id, "google_calendar")
    if not token:
        return 0

    task_lists = await _list_google_task_lists(token)
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

    existing_by_key: dict[tuple[str, str], Task] = {}
    for local_task in existing_tasks:
        if local_task.google_task_id:
            existing_by_key[
                (
                    local_task.google_task_list_id or GOOGLE_DEFAULT_TASKLIST_ID,
                    local_task.google_task_id,
                )
            ] = local_task

    changed_count = 0

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
            local = existing_by_key.get((task_list_id, google_task_id))

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
            due_date_value, due_time_value = _google_due_to_task_fields(google_task.get("due"))
            is_completed = str(google_task.get("status") or "").lower() == "completed"
            completed_at = (
                _parse_google_datetime(google_task.get("completed")) if is_completed else None
            )
            remote_updated_at = _parse_google_datetime(google_task.get("updated"))

            if local:
                if not _is_google_task_newer(local, remote_updated_at):
                    continue

                changed = False
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

                if local.google_task_list_id != task_list_id:
                    local.google_task_list_id = task_list_id
                    changed = True
                if local.google_task_id != google_task_id:
                    local.google_task_id = google_task_id
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

    try:
        return run_async(
            _sync_google_tasks_for_user_async(db, user_id=user_id, org_id=org_id),
            timeout=45,
        )
    except Exception as exc:
        logger.warning(
            "Google→Platform task sync failed user=%s org=%s error=%s", user_id, org_id, exc
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
