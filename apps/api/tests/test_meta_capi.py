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


def _capi_ad(db, org_id):
    from app.db.models import MetaAd, MetaAdAccount, MetaAdSet, MetaCampaign

    account = MetaAdAccount(
        organization_id=org_id,
        ad_account_external_id="act_capi_test",
        pixel_id="pixel_capi_test",
        capi_enabled=True,
        is_active=True,
    )
    db.add(account)
    db.flush()
    campaign = MetaCampaign(
        organization_id=org_id,
        ad_account_id=account.id,
        campaign_external_id="campaign_capi_test",
        campaign_name="CAPI Test Campaign",
        status="ACTIVE",
    )
    db.add(campaign)
    db.flush()
    adset = MetaAdSet(
        organization_id=org_id,
        ad_account_id=account.id,
        campaign_id=campaign.id,
        campaign_external_id=campaign.campaign_external_id,
        adset_external_id="adset_capi_test",
        adset_name="CAPI Test Ad Set",
        status="ACTIVE",
    )
    db.add(adset)
    db.flush()
    ad = MetaAd(
        organization_id=org_id,
        ad_account_id=account.id,
        campaign_id=campaign.id,
        adset_id=adset.id,
        campaign_external_id=campaign.campaign_external_id,
        adset_external_id=adset.adset_external_id,
        ad_external_id="ad_capi_test",
        ad_name="CAPI Test Ad",
        status="ACTIVE",
    )
    db.add(ad)
    db.flush()
    return account, ad


@pytest.mark.asyncio
async def test_enabled_capi_job_resolves_token_and_sends_stage_event(db, test_org, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    from uuid import uuid4

    from pydantic import SecretStr

    from app.jobs.handlers import meta
    from app.services import meta_token_service

    account, ad = _capi_ad(db, test_org.id)

    monkeypatch.setattr(meta_capi.settings, "META_CAPI_ENABLED", True)
    monkeypatch.setattr(meta_capi.settings, "META_TEST_MODE", False)
    monkeypatch.setattr(meta_capi.settings, "META_APP_SECRET", SecretStr(""))
    monkeypatch.setattr(
        meta_capi, "map_stage_key_to_meta_status_for_org", lambda *args: "Qualified"
    )
    token_resolver = Mock(
        return_value=meta_token_service.TokenResult(
            token="capi-test-token", connection_id=None, needs_reauth=False
        )
    )
    monkeypatch.setattr(meta_token_service, "get_capi_token_for_account", token_resolver)
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post.return_value = SimpleNamespace(status_code=200, json=lambda: {"events_received": 1})
    monkeypatch.setattr(meta_capi.httpx, "AsyncClient", lambda **kwargs: client)
    job = SimpleNamespace(
        id=uuid4(),
        organization_id=test_org.id,
        payload={
            "meta_lead_id": "capi-test-lead",
            "meta_ad_external_id": ad.ad_external_id,
            "surrogate_status": "approved",
        },
    )

    await meta.process_meta_capi_event(db, job)

    token_resolver.assert_called_once_with(db, account)
    client.post.assert_awaited_once()
    url = client.post.await_args.args[0]
    payload = client.post.await_args.kwargs["json"]
    assert url == f"{meta_capi.CAPI_URL}/{account.pixel_id}/events"
    assert payload["access_token"] == "capi-test-token"
    event = payload["data"][0]
    assert event["user_data"] == {"lead_id": "capi-test-lead"}
    assert event["custom_data"] == {"lead_status": "Qualified", "crm_status": "approved"}
    assert event["event_id"] == "capi_capi-test-lead_qualified"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mismatched_account_link", [False, True], ids=["foreign-ad", "foreign-account"]
)
async def test_capi_job_cannot_send_through_another_organization(
    db, test_org, monkeypatch, mismatched_account_link
):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from uuid import uuid4

    from app.db.models import Organization
    from app.jobs.handlers import meta
    from app.services import meta_token_service

    foreign_org = Organization(name="Foreign CAPI Organization", slug=f"foreign-capi-{uuid4().hex}")
    db.add(foreign_org)
    db.flush()
    _account, ad = _capi_ad(db, foreign_org.id)
    if mismatched_account_link:
        ad.organization_id = test_org.id
        db.flush()

    monkeypatch.setattr(meta_capi.settings, "META_CAPI_ENABLED", True)
    monkeypatch.setattr(meta_capi.settings, "META_TEST_MODE", False)
    monkeypatch.setattr(
        meta_capi, "map_stage_key_to_meta_status_for_org", lambda *args: "Qualified"
    )
    token_resolver = Mock(side_effect=AssertionError("Foreign account reached token resolution"))
    http_client = Mock(side_effect=AssertionError("Foreign account reached provider HTTP"))
    monkeypatch.setattr(meta_token_service, "get_capi_token_for_account", token_resolver)
    monkeypatch.setattr(meta_capi.httpx, "AsyncClient", http_client)
    job = SimpleNamespace(
        id=uuid4(),
        organization_id=test_org.id,
        payload={
            "meta_lead_id": "capi-test-lead",
            "meta_ad_external_id": ad.ad_external_id,
            "surrogate_status": "approved",
        },
    )

    await meta.process_meta_capi_event(db, job)

    token_resolver.assert_not_called()
    http_client.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["response", "exception"])
async def test_capi_job_sanitizes_provider_failures(db, test_org, monkeypatch, caplog, failure):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.jobs.handlers import meta
    from app.services import meta_token_service

    account, ad = _capi_ad(db, test_org.id)
    marker = "private-person@example.test provider-secret-token"
    monkeypatch.setattr(meta_capi.settings, "META_CAPI_ENABLED", True)
    monkeypatch.setattr(meta_capi.settings, "META_TEST_MODE", False)
    monkeypatch.setattr(
        meta_capi, "map_stage_key_to_meta_status_for_org", lambda *args: "Qualified"
    )
    monkeypatch.setattr(
        meta_token_service,
        "get_capi_token_for_account",
        lambda *args: meta_token_service.TokenResult(
            token="test-token", connection_id=None, needs_reauth=False
        ),
    )
    client = AsyncMock()
    client.__aenter__.return_value = client
    if failure == "response":
        client.post.return_value = SimpleNamespace(status_code=400, text=marker)
    else:
        client.post.side_effect = RuntimeError(marker)
    monkeypatch.setattr(meta_capi.httpx, "AsyncClient", lambda **kwargs: client)
    job = SimpleNamespace(
        id=uuid4(),
        organization_id=test_org.id,
        payload={
            "meta_lead_id": "capi-test-lead",
            "meta_ad_external_id": ad.ad_external_id,
            "surrogate_status": "approved",
        },
    )
    with pytest.raises(Exception) as raised:
        await meta.process_meta_capi_event(db, job)
    assert client.post.await_count == 1
    assert marker not in str(raised.value)
    assert marker not in caplog.text
    assert marker not in (account.last_error or "")
    assert account.last_error in {"CAPI: CAPI error 400", "CAPI: Meta CAPI request failed"}
