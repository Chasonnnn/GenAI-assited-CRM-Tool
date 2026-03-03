from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.enums import OwnerType, TaskType
from app.db.models import Task
from app.services import calendar_service, google_tasks_sync_service


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.content = b"1" if payload is not None else b""

    def json(self):
        return self._payload


class _AsyncClientFactory:
    def __init__(self, request_handler):
        self._handler = request_handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, headers=None, params=None, json=None):
        return await self._handler(method=method, url=url, headers=headers, params=params, json=json)

    async def get(self, url, headers=None, params=None):
        return await self._handler(method="GET", url=url, headers=headers, params=params, json=None)

    async def post(self, url, headers=None, params=None, json=None, timeout=None):
        del timeout
        return await self._handler(method="POST", url=url, headers=headers, params=params, json=json)

    async def put(self, url, headers=None, params=None, json=None):
        return await self._handler(method="PUT", url=url, headers=headers, params=params, json=json)

    async def delete(self, url, headers=None, params=None):
        return await self._handler(method="DELETE", url=url, headers=headers, params=params, json=None)


def _make_task(**overrides) -> Task:
    base = {
        "id": uuid4(),
        "organization_id": uuid4(),
        "created_by_user_id": uuid4(),
        "owner_type": OwnerType.USER.value,
        "owner_id": uuid4(),
        "title": "Task",
        "description": "desc",
        "task_type": TaskType.OTHER.value,
        "due_date": date(2026, 1, 2),
        "due_time": time(9, 30),
        "is_completed": False,
        "google_task_id": None,
        "google_task_list_id": None,
        "google_task_updated_at": None,
        "surrogate_id": None,
        "intended_parent_id": None,
        "workflow_execution_id": None,
    }
    base.update(overrides)
    return Task(**base)


def test_google_task_helper_conversions():
    naive = datetime(2026, 1, 2, 3, 4, 5)
    aware = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    assert google_tasks_sync_service._to_utc(None) is None
    assert google_tasks_sync_service._to_utc(naive).tzinfo == timezone.utc
    assert google_tasks_sync_service._to_utc(aware) == aware
    assert google_tasks_sync_service._parse_google_datetime("2026-01-02T03:04:05Z") is not None
    assert google_tasks_sync_service._parse_google_datetime("bad-date") is None
    assert google_tasks_sync_service._to_google_datetime(aware).endswith("Z")
    assert google_tasks_sync_service._encode_google_id("a/b c") == "a%2Fb%20c"

    due_date, due_time = google_tasks_sync_service._google_due_to_task_fields("2026-01-05T00:00:00Z")
    assert due_date == date(2026, 1, 5)
    assert due_time is None

    due_date, due_time = google_tasks_sync_service._google_due_to_task_fields("2026-01-05T09:45:00Z")
    assert due_date == date(2026, 1, 5)
    assert due_time == time(9, 45)


def test_google_task_payload_and_sync_predicates():
    task = _make_task(is_completed=True, completed_at=datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc))
    payload = google_tasks_sync_service._build_google_task_payload(task)
    assert payload["status"] == "completed"
    assert "due" in payload
    assert "completed" in payload

    assert google_tasks_sync_service._should_sync_task_to_google(task) is True
    workflow_task = _make_task(task_type=TaskType.WORKFLOW_APPROVAL.value)
    assert google_tasks_sync_service._should_sync_task_to_google(workflow_task) is False

    assert google_tasks_sync_service._task_can_be_deleted_from_google_signal(task) is True
    linked = _make_task(surrogate_id=uuid4())
    assert google_tasks_sync_service._task_can_be_deleted_from_google_signal(linked) is False


@pytest.mark.asyncio
async def test_google_request_success_error_and_exception(monkeypatch):
    async def _handler(**kwargs):
        path = kwargs["url"]
        if path.endswith("/ok"):
            return _FakeResponse(200, {"items": []})
        if path.endswith("/err"):
            return _FakeResponse(403, {"error": {"message": "denied"}})
        raise RuntimeError("network")

    monkeypatch.setattr(
        google_tasks_sync_service.httpx,
        "AsyncClient",
        lambda timeout=30.0: _AsyncClientFactory(_handler),
    )

    code, payload = await google_tasks_sync_service._google_request(
        access_token="tok",
        method="GET",
        path="/ok",
    )
    assert code == 200
    assert payload == {"items": []}

    code, payload = await google_tasks_sync_service._google_request(
        access_token="tok",
        method="GET",
        path="/err",
    )
    assert code == 403
    assert payload == {"error": {"message": "denied"}}

    code, payload = await google_tasks_sync_service._google_request(
        access_token="tok",
        method="GET",
        path="/explode",
    )
    assert code == 0
    assert payload is None


@pytest.mark.asyncio
async def test_google_list_helpers(monkeypatch):
    list_calls = {"lists": 0, "tasks": 0}

    async def _fake_request(*, access_token, method, path, params=None, json_body=None):
        del access_token, method, params, json_body
        if path == "/users/@me/lists":
            list_calls["lists"] += 1
            if list_calls["lists"] == 1:
                return 200, {"items": [{"id": "L1"}], "nextPageToken": "n"}
            return 200, {"items": [{"id": "L2"}]}
        if path.endswith("/tasks"):
            list_calls["tasks"] += 1
            if list_calls["tasks"] == 1:
                return 200, {"items": [{"id": "T1"}], "nextPageToken": "x"}
            return 200, {"items": [{"id": "T2"}]}
        return 500, None

    monkeypatch.setattr(google_tasks_sync_service, "_google_request", _fake_request)

    lists, list_error = await google_tasks_sync_service._list_google_task_lists("tok")
    assert list_error is None
    assert [item["id"] for item in lists] == ["L1", "L2"]

    tasks = await google_tasks_sync_service._list_google_tasks("tok", "L1")
    assert [item["id"] for item in tasks] == ["T1", "T2"]


@pytest.mark.asyncio
async def test_google_task_lists_returns_error_tuple_for_insufficient_scopes(monkeypatch):
    async def _fake_request(*, access_token, method, path, params=None, json_body=None):
        del access_token, method, params, json_body
        if path == "/users/@me/lists":
            return 403, {"error": {"message": "Request had insufficient authentication scopes."}}
        return 500, None

    monkeypatch.setattr(google_tasks_sync_service, "_google_request", _fake_request)

    lists, list_error = await google_tasks_sync_service._list_google_task_lists("tok")
    assert lists == []
    assert list_error is not None
    assert list_error["status_code"] == 403


@pytest.mark.asyncio
async def test_google_upsert_delete_and_access_paths(monkeypatch, db):
    task = _make_task(owner_id=uuid4(), google_task_id="remote-1", google_task_list_id="default")

    async def _token(*args, **kwargs):
        return "tok"

    calls: list[str] = []

    async def _fake_request(*, access_token, method, path, params=None, json_body=None):
        del access_token, params, json_body
        calls.append(f"{method}:{path}")
        if method == "PATCH":
            return 404, None
        if method == "POST":
            return 201, {"id": "created-1", "updated": "2026-01-03T10:00:00Z"}
        if method == "DELETE":
            return 204, None
        return 200, {"items": []}

    monkeypatch.setattr(google_tasks_sync_service.oauth_service, "get_access_token_async", _token)
    monkeypatch.setattr(google_tasks_sync_service, "_google_request", _fake_request)

    upsert = await google_tasks_sync_service._upsert_google_task_for_platform_task(task, db)
    assert upsert is not None
    assert upsert[0] == "created-1"
    assert any(item.startswith("PATCH:") for item in calls)
    assert any(item.startswith("POST:") for item in calls)

    deleted = await google_tasks_sync_service._delete_google_task_for_platform_task(task, db)
    assert deleted is True

    monkeypatch.setattr(
        google_tasks_sync_service.oauth_service,
        "get_user_integration",
        lambda *_args, **_kwargs: SimpleNamespace(id=uuid4()),
    )
    def _run_probe_ok(coro, timeout=20):
        del timeout
        coro.close()
        return True, None

    monkeypatch.setattr(google_tasks_sync_service, "run_async", _run_probe_ok)
    ok, reason = google_tasks_sync_service.check_google_tasks_access(db, uuid4())
    assert ok is True
    assert reason is None

    def _run_probe_fail(coro, timeout=20):
        del timeout
        coro.close()
        raise RuntimeError("probe failed")

    monkeypatch.setattr(google_tasks_sync_service, "run_async", _run_probe_fail)
    ok, reason = google_tasks_sync_service.check_google_tasks_access(db, uuid4())
    assert ok is False
    assert reason == "probe_failed"


def test_sync_platform_task_wrappers(monkeypatch, db):
    task = _make_task(owner_id=uuid4())
    task.google_task_updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    monkeypatch.setattr(
        google_tasks_sync_service.oauth_service,
        "get_user_integration",
        lambda *_args, **_kwargs: SimpleNamespace(id=uuid4()),
    )
    def _run_async_success(coro, timeout=30):
        del timeout
        coro.close()
        return ("new-remote", "default", datetime(2026, 1, 2, tzinfo=timezone.utc))

    monkeypatch.setattr(google_tasks_sync_service, "run_async", _run_async_success)
    google_tasks_sync_service.sync_platform_task_to_google(db, task)
    assert task.google_task_id == "new-remote"
    assert task.google_task_list_id == "default"

    task.google_task_id = "remote-1"
    def _run_async_fail(coro, timeout=30):
        del timeout
        coro.close()
        raise RuntimeError("sync fail")

    monkeypatch.setattr(google_tasks_sync_service, "run_async", _run_async_fail)
    google_tasks_sync_service.delete_platform_task_from_google(db, task)

    remote_newer = google_tasks_sync_service._is_google_task_newer(
        task, datetime(2026, 1, 3, tzinfo=timezone.utc)
    )
    assert remote_newer is True


@pytest.mark.asyncio
async def test_sync_google_tasks_marks_scope_missing_after_403(db, test_auth, monkeypatch):
    from app.db.models import UserIntegration

    integration = UserIntegration(
        user_id=test_auth.user.id,
        integration_type="google_calendar",
        access_token_encrypted="token-1",
        refresh_token_encrypted="token-2",
        granted_scopes=None,
    )
    db.add(integration)
    db.commit()

    async def _token(*_args, **_kwargs):
        return "tok"

    async def _fake_request(*, access_token, method, path, params=None, json_body=None):
        del access_token, method, params, json_body
        if path == "/users/@me/lists":
            return 403, {"error": {"message": "Request had insufficient authentication scopes."}}
        return 500, None

    monkeypatch.setattr(google_tasks_sync_service.oauth_service, "get_access_token_async", _token)
    monkeypatch.setattr(google_tasks_sync_service, "_google_request", _fake_request)

    changed = await google_tasks_sync_service.sync_google_tasks_for_user_async(
        db,
        user_id=test_auth.user.id,
        org_id=test_auth.org.id,
    )
    assert changed == 0

    db.refresh(integration)
    assert integration.granted_scopes == []


def test_calendar_watch_helper_functions(monkeypatch):
    monkeypatch.setattr(calendar_service.settings, "API_BASE_URL", "https://api.example.com")
    assert calendar_service._calendar_events_endpoint("primary").endswith("/calendars/primary/events")
    assert "/events/" in calendar_service._calendar_event_endpoint("primary", "evt 1")
    assert calendar_service._channel_stop_endpoint().endswith("/channels/stop")
    assert calendar_service._google_calendar_webhook_address() == "https://api.example.com/webhooks/google-calendar"

    exp = calendar_service._parse_google_watch_expiration("1735689600000")
    assert exp is not None
    assert calendar_service._parse_google_watch_expiration("bad") is None
    assert calendar_service._watch_is_fresh(datetime.now(timezone.utc) + timedelta(days=1), renew_before=timedelta(hours=1))
    assert calendar_service._watch_is_fresh(None, renew_before=timedelta(hours=1)) is False


def test_calendar_verify_watch_token(monkeypatch):
    monkeypatch.setattr(calendar_service.oauth_service, "decrypt_token", lambda value: f"plain:{value}")
    monkeypatch.setattr(calendar_service, "verify_secret", lambda provided, expected: provided == expected)
    assert calendar_service.verify_watch_channel_token("enc", "plain:enc") is True
    assert calendar_service.verify_watch_channel_token("enc", "wrong") is False
    assert calendar_service.verify_watch_channel_token(None, "x") is False


@pytest.mark.asyncio
async def test_calendar_watch_http_paths(monkeypatch):
    async def _handler(**kwargs):
        if kwargs["url"].endswith("/watch"):
            return _FakeResponse(
                200,
                {"resourceId": "resource-1", "expiration": "1735689600000"},
            )
        return _FakeResponse(204, {})

    monkeypatch.setattr(calendar_service.settings, "API_BASE_URL", "https://api.example.com")
    monkeypatch.setattr(
        calendar_service.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _AsyncClientFactory(_handler),
    )

    watch = await calendar_service._post_google_events_watch(
        access_token="tok",
        calendar_id="primary",
        channel_id="chan-1",
        channel_token="token",
        ttl_seconds=30,
    )
    assert watch is not None
    assert watch["resource_id"] == "resource-1"

    stopped = await calendar_service._post_google_channel_stop(
        access_token="tok",
        channel_id="chan-1",
        resource_id="resource-1",
    )
    assert stopped is True


@pytest.mark.asyncio
async def test_calendar_watch_stateful_flows(monkeypatch, db):
    user_id = uuid4()
    integration = SimpleNamespace(
        google_calendar_channel_id="old-channel",
        google_calendar_resource_id="old-resource",
        google_calendar_channel_token_encrypted="enc-token",
        google_calendar_watch_expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        updated_at=None,
    )
    monkeypatch.setattr(calendar_service.oauth_service, "get_user_integration", lambda *_args, **_kwargs: integration)
    async def _token(*_args, **_kwargs):
        return "tok"

    monkeypatch.setattr(calendar_service, "get_google_access_token", _token)
    async def _stop_channel(**kwargs):
        return True

    monkeypatch.setattr(calendar_service, "_post_google_channel_stop", _stop_channel)
    monkeypatch.setattr(calendar_service.oauth_service, "encrypt_token", lambda value: f"enc:{value}")

    renewed = await calendar_service.ensure_google_calendar_watch(
        db=db,
        user_id=user_id,
        renew_before=timedelta(hours=1),
    )
    # Fresh watch metadata should skip renewal with a short renew window.
    assert renewed is False

    async def _start_watch(**kwargs):
        return {
            "channel_id": "new",
            "resource_id": "res",
            "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        }

    monkeypatch.setattr(calendar_service, "_post_google_events_watch", _start_watch)
    renewed = await calendar_service.ensure_google_calendar_watch(
        db=db,
        user_id=user_id,
        renew_before=timedelta(days=100),
    )
    assert renewed is True
    assert integration.google_calendar_channel_id == "new"

    stopped = await calendar_service.stop_google_calendar_watch(db, user_id)
    assert stopped is True
    assert integration.google_calendar_channel_id is None


@pytest.mark.asyncio
async def test_calendar_event_crud_and_meet(monkeypatch):
    start = datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc)
    state = {"stored_event": None}

    async def _handler(**kwargs):
        method = kwargs["method"]
        url = kwargs["url"]
        if method == "POST" and url.endswith("/events"):
            if kwargs.get("params", {}).get("conferenceDataVersion") == "1":
                return _FakeResponse(
                    201,
                    {
                        "id": "meet-1",
                        "conferenceData": {
                            "entryPoints": [{"entryPointType": "video", "uri": "https://meet.google.com/abc"}]
                        },
                    },
                )
            payload = {
                "id": "evt-1",
                "summary": kwargs["json"]["summary"],
                "start": {"dateTime": kwargs["json"]["start"]["dateTime"]},
                "end": {"dateTime": kwargs["json"]["end"]["dateTime"]},
                "htmlLink": "https://calendar/event",
            }
            state["stored_event"] = payload
            return _FakeResponse(201, payload)
        if method == "GET":
            return _FakeResponse(200, state["stored_event"])
        if method == "PUT":
            body = kwargs["json"]
            payload = {
                "id": "evt-1",
                "summary": body.get("summary", "Updated"),
                "start": {"dateTime": body["start"]["dateTime"]},
                "end": {"dateTime": body["end"]["dateTime"]},
                "htmlLink": "https://calendar/event-updated",
            }
            state["stored_event"] = payload
            return _FakeResponse(200, payload)
        if method == "DELETE":
            return _FakeResponse(204, {})
        return _FakeResponse(500, {})

    monkeypatch.setattr(
        calendar_service.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _AsyncClientFactory(_handler),
    )

    created = await calendar_service.create_google_event(
        access_token="tok",
        calendar_id="primary",
        summary="Check-in",
        start_time=start,
        end_time=end,
        attendee_emails=["client@example.com"],
    )
    assert created is not None
    assert created["id"] == "evt-1"

    updated = await calendar_service.update_google_event(
        access_token="tok",
        calendar_id="primary",
        event_id="evt-1",
        summary="Updated Check-in",
        start_time=start + timedelta(hours=1),
        end_time=end + timedelta(hours=1),
    )
    assert updated is not None
    assert updated["summary"] == "Updated Check-in"

    deleted = await calendar_service.delete_google_event(
        access_token="tok",
        calendar_id="primary",
        event_id="evt-1",
    )
    assert deleted is True

    meet = await calendar_service.create_google_meet_link(
        access_token="tok",
        calendar_id="primary",
        summary="Meet",
        start_time=start,
        end_time=end,
        attendee_emails=["client@example.com"],
    )
    assert meet["event_id"] == "meet-1"
    assert meet["meet_url"].startswith("https://meet.google.com/")
