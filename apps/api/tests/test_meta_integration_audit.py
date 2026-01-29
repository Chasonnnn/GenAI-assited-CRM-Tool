from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_meta_lead_fetch_does_not_auto_convert_without_mapping(db, test_org, monkeypatch):
    from app.core.encryption import encrypt_token
    from app.db.enums import JobType
    from app.db.models import Job, MetaPageMapping
    from app.services import meta_api, meta_lead_service
    from app.worker import process_meta_lead_fetch

    mapping = MetaPageMapping(
        organization_id=test_org.id,
        page_id="123456789",
        access_token_encrypted=encrypt_token("test-token"),
        is_active=True,
    )
    db.add(mapping)
    db.commit()

    job = Job(
        organization_id=test_org.id,
        job_type=JobType.META_LEAD_FETCH.value,
        payload={"leadgen_id": "lead-123", "page_id": "123456789"},
    )
    db.add(job)
    db.commit()

    async def fake_fetch(leadgen_id: str, access_token: str):
        return (
            {
                "id": leadgen_id,
                "created_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000"),
                "field_data": [
                    {"name": "full_name", "values": ["Test User"]},
                    {"name": "email", "values": ["test@example.com"]},
                ],
                "form_id": "form_1",
                "page_id": "123456789",
                "ad_id": "ad_1",
            },
            None,
        )

    monkeypatch.setattr(meta_api, "fetch_lead_details", fake_fetch)

    called = {"value": False}

    def fake_convert(
        db, meta_lead, mapping_rules, unknown_column_behavior="metadata", user_id=None
    ):
        called["value"] = True
        return SimpleNamespace(surrogate_number="S10001"), None

    monkeypatch.setattr(meta_lead_service, "convert_to_surrogate_with_mapping", fake_convert)

    await process_meta_lead_fetch(db, job)

    assert called["value"] is False


@pytest.mark.asyncio
async def test_meta_hierarchy_sync_job_raises_on_error(db, test_org, monkeypatch):
    from app.db.enums import JobType
    from app.db.models import Job, MetaAdAccount
    from app.services import meta_sync_service
    from app.worker import process_meta_hierarchy_sync

    account = MetaAdAccount(
        organization_id=test_org.id,
        ad_account_external_id="act_123",
        ad_account_name="Test Account",
        is_active=True,
    )
    db.add(account)
    db.commit()

    job = Job(
        organization_id=test_org.id,
        job_type=JobType.META_HIERARCHY_SYNC.value,
        payload={"ad_account_id": str(account.id), "full_sync": False},
    )
    db.add(job)
    db.commit()

    async def fake_sync(db, ad_account, full_sync=False):
        return {"error": "sync failed"}

    monkeypatch.setattr(meta_sync_service, "sync_hierarchy", fake_sync)

    with pytest.raises(Exception):
        await process_meta_hierarchy_sync(db, job)


@pytest.mark.asyncio
async def test_meta_spend_sync_job_raises_on_error(db, test_org, monkeypatch):
    from app.db.enums import JobType
    from app.db.models import Job, MetaAdAccount
    from app.services import meta_sync_service
    from app.worker import process_meta_spend_sync

    account = MetaAdAccount(
        organization_id=test_org.id,
        ad_account_external_id="act_456",
        ad_account_name="Spend Account",
        is_active=True,
    )
    db.add(account)
    db.commit()

    job = Job(
        organization_id=test_org.id,
        job_type=JobType.META_SPEND_SYNC.value,
        payload={"ad_account_id": str(account.id), "sync_type": "daily"},
    )
    db.add(job)
    db.commit()

    async def fake_sync(db, ad_account, date_start, date_end):
        return {"error": "sync failed"}

    monkeypatch.setattr(meta_sync_service, "sync_spend", fake_sync)

    with pytest.raises(Exception):
        await process_meta_spend_sync(db, job)


@pytest.mark.asyncio
async def test_meta_form_sync_job_raises_on_error(db, test_org, monkeypatch):
    from app.db.enums import JobType
    from app.db.models import Job
    from app.services import meta_sync_service
    from app.worker import process_meta_form_sync

    job = Job(
        organization_id=test_org.id,
        job_type=JobType.META_FORM_SYNC.value,
        payload={"page_ids": ["page_1"]},
    )
    db.add(job)
    db.commit()

    async def fake_sync(db, org_id, page_id=None):
        return {"error": "sync failed"}

    monkeypatch.setattr(meta_sync_service, "sync_forms", fake_sync)

    with pytest.raises(Exception):
        await process_meta_form_sync(db, job)


@pytest.mark.asyncio
async def test_meta_forms_sync_records_decrypt_error(db, test_org, monkeypatch):
    from app.db.models import MetaPageMapping
    from app.services import meta_sync_service, meta_token_service

    mapping = MetaPageMapping(
        organization_id=test_org.id,
        page_id="page_123",
        access_token_encrypted="bad-token",
        is_active=True,
    )
    db.add(mapping)
    db.commit()

    def fake_decrypt(_token: str):
        raise Exception("decrypt failed")

    monkeypatch.setattr(meta_token_service, "decrypt_token", fake_decrypt)

    result = await meta_sync_service.sync_forms(db, test_org.id)
    assert result["error"] is None

    db.refresh(mapping)
    assert mapping.last_error is not None
    assert mapping.last_error_at is not None


@pytest.mark.asyncio
async def test_meta_capi_global_disable_skips(monkeypatch):
    from app.services import meta_capi

    monkeypatch.setattr(meta_capi.settings, "META_CAPI_ENABLED", False)

    class FailingClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("HTTP client should not be constructed")

    monkeypatch.setattr(meta_capi, "httpx", SimpleNamespace(AsyncClient=FailingClient))

    ad_account = SimpleNamespace(
        capi_enabled=True,
        pixel_id="pixel_123",
        ad_account_external_id="act_999",
    )

    success, error = await meta_capi.send_lead_event_for_account(
        lead_id="lead_123",
        ad_account=ad_account,
    )

    assert success is True
    assert error is None


@pytest.mark.asyncio
async def test_get_meta_spend_summary_uses_stored_data(db, test_org):
    from app.db.models import MetaAdAccount, MetaDailySpend
    from app.services import analytics_meta_service

    account = MetaAdAccount(
        organization_id=test_org.id,
        ad_account_external_id="act_789",
        ad_account_name="Spend Test",
        is_active=True,
    )
    db.add(account)
    db.flush()

    spend_date = date.today() - timedelta(days=1)
    row = MetaDailySpend(
        organization_id=test_org.id,
        ad_account_id=account.id,
        spend_date=spend_date,
        campaign_external_id="camp_1",
        campaign_name="Campaign One",
        breakdown_type="_total",
        breakdown_value="_all",
        spend=Decimal("100.00"),
        impressions=100,
        reach=80,
        clicks=10,
        leads=5,
    )
    db.add(row)
    db.commit()

    start = datetime.combine(spend_date, datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(spend_date, datetime.min.time(), tzinfo=timezone.utc)

    result = await analytics_meta_service.get_meta_spend_summary(
        db=db,
        organization_id=test_org.id,
        start=start,
        end=end,
    )

    assert result["total_spend"] == 100.0
    assert result["total_impressions"] == 100
    assert result["total_leads"] == 5
    assert result["cost_per_lead"] == 20.0


def test_production_requires_meta_verify_token():
    from app.core.config import Settings

    with pytest.raises(ValueError) as exc:
        Settings(
            ENV="production",
            DATABASE_URL="postgresql+psycopg://user:pass@db:5432/db",
            JWT_SECRET="super-secret",
            DEV_SECRET="dev-secret",
            API_BASE_URL="https://api.example.com",
            FRONTEND_URL="https://app.example.com",
            CORS_ORIGINS="https://app.example.com",
            GOOGLE_REDIRECT_URI="https://api.example.com/auth/google/callback",
            ZOOM_REDIRECT_URI="https://api.example.com/integrations/zoom/callback",
            GMAIL_REDIRECT_URI="https://api.example.com/integrations/gmail/callback",
            GOOGLE_CALENDAR_REDIRECT_URI="https://api.example.com/integrations/google-calendar/callback",
            GCP_REDIRECT_URI="https://api.example.com/integrations/gcp/callback",
            DUO_REDIRECT_URI="https://app.example.com/auth/duo/callback",
            META_VERIFY_TOKEN="",
            META_ENCRYPTION_KEY="key",
            FERNET_KEY="key",
            DATA_ENCRYPTION_KEY="key",
            PII_HASH_KEY="key",
            ATTACHMENT_SCAN_ENABLED=True,
            GCP_MONITORING_ENABLED=True,
            GCP_PROJECT_ID="test-project",
        )

    assert "META_VERIFY_TOKEN" in str(exc.value)
