import pytest

from app.services import meta_capi


@pytest.mark.parametrize(
    "status,expected",
    [
        ("contacted", meta_capi.META_STATUS_INTAKE),
        ("pre_qualified", meta_capi.META_STATUS_INTAKE),
        ("interview_scheduled", meta_capi.META_STATUS_INTAKE),
        ("application_submitted", meta_capi.META_STATUS_QUALIFIED),
        ("approved", meta_capi.META_STATUS_QUALIFIED),
        ("ready_to_match", meta_capi.META_STATUS_QUALIFIED),
        ("delivered", meta_capi.META_STATUS_QUALIFIED),
        ("disqualified", meta_capi.META_STATUS_DISQUALIFIED),
        ("lost", meta_capi.META_STATUS_LOST),
    ],
)
def test_map_case_status_to_meta_status(status, expected):
    assert meta_capi.map_surrogate_status_to_meta_status(status) == expected


@pytest.mark.parametrize(
    "status",
    ["new_unread", "archived", "restored", ""],
)
def test_map_case_status_to_meta_status_unknown(status):
    assert meta_capi.map_surrogate_status_to_meta_status(status) is None


@pytest.mark.parametrize(
    "from_status,to_status,expected",
    [
        ("new_unread", "contacted", True),
        ("contacted", "pre_qualified", False),
        ("pre_qualified", "application_submitted", True),
        ("application_submitted", "under_review", False),
        ("approved", "ready_to_match", False),
        ("contacted", "disqualified", True),
        ("disqualified", "ready_to_match", True),
        ("", "contacted", True),
        ("archived", "restored", False),
    ],
)
def test_should_send_capi_event(from_status, to_status, expected):
    assert meta_capi.should_send_capi_event(from_status, to_status) is expected


def _meta_surrogate(db, org_id, user_id, *, meta_lead_id):
    from datetime import UTC, datetime

    from app.db.enums import SurrogateSource
    from app.db.models import MetaLead
    from app.schemas.surrogate import SurrogateCreate
    from app.services import surrogate_service

    meta_lead = MetaLead(
        organization_id=org_id,
        meta_lead_id=meta_lead_id,
        meta_form_id="form_1",
        meta_page_id="page_1",
        field_data={},
        field_data_raw={},
        received_at=datetime.now(UTC),
    )
    db.add(meta_lead)
    db.commit()
    surrogate = surrogate_service.create_surrogate(
        db,
        org_id,
        user_id,
        SurrogateCreate(
            full_name="Capi Lead",
            email=f"capi-{meta_lead_id}@example.com",
            source=SurrogateSource.META,
        ),
    )
    surrogate.meta_lead_id = meta_lead.id
    db.commit()
    return surrogate


@pytest.mark.parametrize(
    ("meta_lead_id", "queued"),
    [("1559954882011881", True), ("zapier-lead-1", False), ("zapier-generated-lead-2", False)],
    ids=["meta-lead-id", "legacy-synthetic", "generated-synthetic"],
)
def test_capi_stage_event_is_not_queued_for_synthetic_meta_lead_ids(
    db, test_org, test_user, monkeypatch, meta_lead_id, queued
):
    from app.db.enums import JobType
    from app.db.models import Job
    from app.services import surrogate_events

    monkeypatch.setattr(meta_capi, "should_send_capi_event_for_org", lambda *args: True)
    surrogate = _meta_surrogate(db, test_org.id, test_user.id, meta_lead_id=meta_lead_id)

    surrogate_events._maybe_send_capi_event(db, surrogate, "", "application_submitted")

    jobs = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.META_CAPI_EVENT.value,
        )
        .count()
    )
    assert jobs == (1 if queued else 0)


@pytest.mark.asyncio
async def test_capi_job_with_synthetic_meta_lead_id_is_not_sent():
    from types import SimpleNamespace
    from uuid import uuid4

    from app.jobs.handlers import meta

    class NoDatabase:
        def query(self, *args, **kwargs):
            pytest.fail("synthetic CAPI job reached ad account lookup")

    job = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        payload={
            "meta_lead_id": "zapier-generated-lead",
            "meta_ad_external_id": "ad-1",
            "surrogate_status": "application_submitted",
        },
    )

    await meta.process_meta_capi_event(NoDatabase(), job)
