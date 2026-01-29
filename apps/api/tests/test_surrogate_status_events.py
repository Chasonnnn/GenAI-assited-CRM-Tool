from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid


from app.db.enums import JobType, Role, SurrogateSource
from app.db.models import MetaLead
from app.schemas.surrogate import SurrogateCreate
from app.services import (
    pipeline_service,
    surrogate_events,
    surrogate_service,
    surrogate_status_service,
)


def _get_stage(db, org_id, slug: str):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
    stage = pipeline_service.get_stage_by_slug(db, pipeline.id, slug)
    assert stage is not None
    return stage


def _create_surrogate(db, org_id, user_id, source=SurrogateSource.MANUAL):
    return surrogate_service.create_surrogate(
        db,
        org_id,
        user_id,
        SurrogateCreate(
            full_name="Status Event Test",
            email=f"status-events-{uuid.uuid4().hex[:8]}@example.com",
            source=source,
        ),
    )


def _event_kwargs(surrogate, new_stage, old_stage=None, user_id=None):
    now = datetime.now(timezone.utc)
    return dict(
        db=None,
        surrogate=surrogate,
        new_stage=new_stage,
        old_stage_id=old_stage.id if old_stage else None,
        old_label=old_stage.label if old_stage else None,
        old_slug=old_stage.slug if old_stage else None,
        user_id=user_id,
        effective_at=now,
        recorded_at=now,
        is_undo=False,
        request_id=None,
        approved_by_user_id=None,
        approved_at=None,
        requested_at=None,
    )


def test_status_change_dispatches_event_bus(monkeypatch, db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    target_stage = _get_stage(db, test_org.id, "contacted")

    called = {"event": False}

    def fake_handler(*_args, **_kwargs):
        called["event"] = True

    monkeypatch.setattr(surrogate_events, "handle_status_changed", fake_handler)

    from app.services import notification_facade

    notified = {"count": 0}

    def mark_notify(*_args, **_kwargs):
        notified["count"] += 1

    monkeypatch.setattr(notification_facade, "notify_surrogate_status_changed", mark_notify)

    surrogate_status_service.change_status(
        db=db,
        surrogate=surrogate,
        new_stage_id=target_stage.id,
        user_id=test_user.id,
        user_role=Role.DEVELOPER,
    )

    assert called["event"] is True
    assert notified["count"] == 0


def test_event_bus_triggers_notification_and_workflow(monkeypatch, db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    new_stage = _get_stage(db, test_org.id, "contacted")

    called = {"notify": False, "workflow": False}

    from app.services import notification_facade, workflow_triggers

    def mark_notify(*_args, **_kwargs):
        called["notify"] = True

    def mark_workflow(*_args, **_kwargs):
        called["workflow"] = True

    monkeypatch.setattr(notification_facade, "notify_surrogate_status_changed", mark_notify)
    monkeypatch.setattr(workflow_triggers, "trigger_status_changed", mark_workflow)

    event_kwargs = _event_kwargs(surrogate, new_stage, user_id=test_user.id)
    event_kwargs["db"] = db
    surrogate_events.handle_status_changed(**event_kwargs)

    assert called["notify"] is True
    assert called["workflow"] is True


def test_event_bus_assigns_pool_queue_on_approved(monkeypatch, db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id)
    approved_stage = _get_stage(db, test_org.id, "approved")

    pool_queue = SimpleNamespace(id=uuid.uuid4())
    called = {"assign": False, "ready": False}

    from app.services import notification_facade, queue_service, workflow_triggers

    def fake_assign(*_args, **_kwargs):
        called["assign"] = True
        return surrogate

    def mark_ready(*_args, **_kwargs):
        called["ready"] = True

    monkeypatch.setattr(queue_service, "get_or_create_surrogate_pool_queue", lambda *_: pool_queue)
    monkeypatch.setattr(queue_service, "assign_surrogate_to_queue", fake_assign)
    monkeypatch.setattr(notification_facade, "notify_surrogate_ready_for_claim", mark_ready)
    monkeypatch.setattr(
        notification_facade, "notify_surrogate_status_changed", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(workflow_triggers, "trigger_status_changed", lambda *_args, **_kwargs: None)

    event_kwargs = _event_kwargs(surrogate, approved_stage, user_id=test_user.id)
    event_kwargs["db"] = db
    surrogate_events.handle_status_changed(**event_kwargs)

    assert called["assign"] is True
    assert called["ready"] is True


def test_event_bus_schedules_meta_capi_job(monkeypatch, db, test_org, test_user):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, source=SurrogateSource.META)
    meta_lead = MetaLead(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        meta_lead_id="lead_123",
        meta_page_id="page_456",
    )
    db.add(meta_lead)
    db.flush()
    surrogate.meta_lead_id = meta_lead.id
    surrogate.meta_ad_external_id = "ad_789"
    db.commit()

    new_stage = _get_stage(db, test_org.id, "contacted")

    from app.services import job_service, meta_capi, notification_facade, workflow_triggers

    scheduled: dict[str, object] = {}

    def fake_schedule_job(*_args, **kwargs):
        scheduled["job_type"] = kwargs.get("job_type")
        scheduled["payload"] = kwargs.get("payload")
        return None

    monkeypatch.setattr(meta_capi, "should_send_capi_event", lambda *_: True)
    monkeypatch.setattr(job_service, "schedule_job", fake_schedule_job)
    monkeypatch.setattr(
        notification_facade, "notify_surrogate_status_changed", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(workflow_triggers, "trigger_status_changed", lambda *_args, **_kwargs: None)

    event_kwargs = _event_kwargs(
        surrogate,
        new_stage,
        old_stage=_get_stage(db, test_org.id, "new_unread"),
        user_id=test_user.id,
    )
    event_kwargs["db"] = db
    surrogate_events.handle_status_changed(**event_kwargs)

    assert scheduled["job_type"] == JobType.META_CAPI_EVENT
    assert scheduled["payload"]["meta_lead_id"] == meta_lead.meta_lead_id
