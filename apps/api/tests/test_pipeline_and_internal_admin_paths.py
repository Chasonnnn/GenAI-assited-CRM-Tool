from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.routers import internal as internal_router
from app.services import pipeline_service


class _SessionCtx:
    def __init__(self, db):
        self._db = db

    def __enter__(self):
        return self._db

    def __exit__(self, exc_type, exc, tb):
        return False


def test_pipeline_service_lifecycle(monkeypatch, db, test_org, test_user):
    version_counter = {"n": 1}

    def _create_version(**kwargs):
        version_counter["n"] += 1
        return SimpleNamespace(version=version_counter["n"])

    monkeypatch.setattr("app.services.version_service.create_version", _create_version)

    default_pipeline = pipeline_service.get_or_create_default_pipeline(
        db, test_org.id, user_id=test_user.id
    )
    assert default_pipeline.is_default is True
    assert len(default_pipeline.stages) > 0

    created = pipeline_service.create_pipeline(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Secondary Pipeline",
    )
    assert created.is_default is False
    assert created.current_version >= 1

    renamed = pipeline_service.update_pipeline_name(
        db,
        created,
        name="Secondary Pipeline Renamed",
        user_id=test_user.id,
        comment="rename test",
    )
    assert renamed.name == "Secondary Pipeline Renamed"

    pipelines = pipeline_service.list_pipelines(db, test_org.id)
    assert len(pipelines) >= 2

    added = pipeline_service.sync_missing_stages(db, created, user_id=test_user.id)
    assert added >= 0

    deleted = pipeline_service.delete_pipeline(db, created)
    assert deleted is True
    assert pipeline_service.delete_pipeline(db, default_pipeline) is False


def test_internal_verify_secret_guard(monkeypatch):
    monkeypatch.setattr(internal_router.settings, "INTERNAL_SECRET", None)
    with pytest.raises(Exception):
        internal_router.verify_internal_secret("secret")

    monkeypatch.setattr(internal_router.settings, "INTERNAL_SECRET", "expected")
    monkeypatch.setattr(
        internal_router, "verify_secret", lambda provided, expected: provided == expected
    )
    with pytest.raises(Exception):
        internal_router.verify_internal_secret("wrong")
    internal_router.verify_internal_secret("expected")


@pytest.mark.asyncio
async def test_internal_scheduled_endpoints(client, db, monkeypatch, test_org):
    monkeypatch.setattr(internal_router.settings, "INTERNAL_SECRET", "secret")
    monkeypatch.setattr(
        internal_router, "verify_secret", lambda provided, expected: provided == expected
    )
    monkeypatch.setattr(internal_router, "SessionLocal", lambda: _SessionCtx(db))

    scheduled_jobs: list[dict] = []
    monkeypatch.setattr(
        internal_router.job_service,
        "schedule_job",
        lambda **kwargs: scheduled_jobs.append(kwargs),
    )
    monkeypatch.setattr(internal_router.org_service, "list_orgs", lambda _db: [test_org])

    # token-check endpoint
    mapping_expired = SimpleNamespace(
        organization_id=test_org.id,
        token_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        page_id="page-expired",
        page_name="Expired Page",
    )
    mapping_soon = SimpleNamespace(
        organization_id=test_org.id,
        token_expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        page_id="page-soon",
        page_name="Soon Page",
    )
    oauth_conn = SimpleNamespace(
        id=uuid4(),
        organization_id=test_org.id,
        token_expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        meta_user_name="Meta User",
        meta_user_id="meta-1",
    )
    monkeypatch.setattr(
        internal_router.meta_page_service,
        "list_active_mappings",
        lambda _db: [mapping_expired, mapping_soon],
    )
    monkeypatch.setattr(
        internal_router.meta_oauth_service,
        "list_active_oauth_connections_any_org",
        lambda _db: [oauth_conn],
    )
    monkeypatch.setattr(internal_router.ops_service, "update_config_status", lambda **kwargs: None)
    monkeypatch.setattr(
        internal_router.ops_service,
        "get_or_create_health",
        lambda **kwargs: SimpleNamespace(status="ok"),
    )
    monkeypatch.setattr(
        internal_router.alert_service, "create_or_update_alert", lambda **kwargs: None
    )

    token_check = await client.post(
        "/internal/scheduled/token-check",
        headers={"X-Internal-Secret": "secret"},
    )
    assert token_check.status_code == 200
    token_data = token_check.json()
    assert token_data["pages_checked"] == 2
    assert token_data["oauth_connections_checked"] == 1

    # workflow sweep endpoints
    workflow_sweep = await client.post(
        "/internal/scheduled/workflow-sweep",
        headers={"X-Internal-Secret": "secret"},
    )
    assert workflow_sweep.status_code == 200
    assert workflow_sweep.json()["orgs_processed"] == 1

    approval_expiry = await client.post(
        "/internal/scheduled/workflow-approval-expiry",
        headers={"X-Internal-Secret": "secret"},
    )
    assert approval_expiry.status_code == 200
    assert approval_expiry.json()["jobs_created"] == 1

    data_purge = await client.post(
        "/internal/scheduled/data-purge",
        headers={"X-Internal-Secret": "secret"},
    )
    assert data_purge.status_code == 200
    assert data_purge.json()["jobs_created"] == 1

    # task notifications + contact reminders
    monkeypatch.setattr(
        internal_router.task_service,
        "list_user_tasks_due_on",
        lambda **kwargs: [
            SimpleNamespace(
                id=uuid4(),
                title="Due Soon",
                organization_id=test_org.id,
                owner_id=uuid4(),
                due_date=datetime.now().date(),
                case=None,
            )
        ],
    )
    monkeypatch.setattr(
        internal_router.task_service,
        "list_user_tasks_overdue",
        lambda **kwargs: [
            SimpleNamespace(
                id=uuid4(),
                title="Overdue",
                organization_id=test_org.id,
                owner_id=uuid4(),
                due_date=datetime.now().date(),
                case=None,
            )
        ],
    )
    monkeypatch.setattr(
        "app.services.notification_service.notify_task_due_soon", lambda **kwargs: None
    )
    monkeypatch.setattr(
        "app.services.notification_service.notify_task_overdue", lambda **kwargs: None
    )
    monkeypatch.setattr(
        internal_router.contact_reminder_service,
        "process_contact_reminder_jobs",
        lambda _db: {
            "orgs_processed": 1,
            "total_surrogates_checked": 3,
            "total_notifications_created": 1,
            "errors": [],
        },
    )

    task_notifs = await client.post(
        "/internal/scheduled/task-notifications",
        headers={"X-Internal-Secret": "secret"},
    )
    assert task_notifs.status_code == 200
    assert task_notifs.json()["notifications_created"] == 2

    contact_reminders = await client.post(
        "/internal/scheduled/contact-reminders",
        headers={"X-Internal-Secret": "secret"},
    )
    assert contact_reminders.status_code == 200
    assert contact_reminders.json()["orgs_processed"] == 1

    # meta sync endpoints
    ad_account = SimpleNamespace(id=uuid4(), organization_id=test_org.id)
    monkeypatch.setattr(
        internal_router.meta_admin_service, "list_active_ad_accounts", lambda _db: [ad_account]
    )

    meta_hierarchy = await client.post(
        "/internal/scheduled/meta-hierarchy-sync",
        headers={"X-Internal-Secret": "secret"},
    )
    assert meta_hierarchy.status_code == 200
    assert meta_hierarchy.json()["jobs_created"] == 1

    meta_spend = await client.post(
        "/internal/scheduled/meta-spend-sync",
        headers={"X-Internal-Secret": "secret"},
    )
    assert meta_spend.status_code == 200
    assert meta_spend.json()["jobs_created"] == 1

    monkeypatch.setattr(
        internal_router.meta_page_service,
        "list_active_mappings",
        lambda _db: [
            SimpleNamespace(organization_id=test_org.id, page_id="p1"),
            SimpleNamespace(organization_id=test_org.id, page_id="p2"),
        ],
    )
    meta_forms = await client.post(
        "/internal/scheduled/meta-forms-sync",
        headers={"X-Internal-Secret": "secret"},
    )
    assert meta_forms.status_code == 200
    assert meta_forms.json()["jobs_created"] == 1

    assert len(scheduled_jobs) >= 6
