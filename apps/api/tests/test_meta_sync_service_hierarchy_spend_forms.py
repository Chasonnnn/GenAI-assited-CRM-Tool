from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.models import (
    MetaAdAccount,
    MetaAdPlatformDaily,
    MetaCampaign,
    MetaForm,
    MetaPageMapping,
    Surrogate,
)
from app.services import meta_api, meta_sync_service


def _create_ad_account(db, org_id, external_id: str | None = None) -> MetaAdAccount:
    ad_account_external_id = external_id or f"act_{uuid4().hex[:8]}"
    account = MetaAdAccount(
        organization_id=org_id,
        ad_account_external_id=ad_account_external_id,
        ad_account_name="Test Account",
        is_active=True,
    )
    db.add(account)
    db.flush()
    return account


class _FakeResponse:
    def __init__(self, status_code: int, data: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._data = data or {}
        self.text = text
        self.headers = {}

    def json(self):
        return self._data


class _FakeAsyncClient:
    def __init__(
        self, responses: list[_FakeResponse] | None = None, error: Exception | None = None
    ):
        self._responses = responses or []
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *_args, **_kwargs):
        if self._error:
            raise self._error
        return self._responses.pop(0) if self._responses else _FakeResponse(200, {"data": []})


def test_meta_upsert_campaign_adset_and_ad(db, test_org):
    account = _create_ad_account(db, test_org.id)

    campaign = meta_sync_service._upsert_campaign(
        db,
        account,
        test_org.id,
        {"id": "cmp_1", "name": "Campaign One", "objective": "LEADS", "status": "ACTIVE"},
    )
    assert campaign is not None
    assert campaign.campaign_name == "Campaign One"

    # Update existing campaign path
    campaign_updated = meta_sync_service._upsert_campaign(
        db,
        account,
        test_org.id,
        {"id": "cmp_1", "name": "Campaign Renamed", "status": "PAUSED"},
    )
    assert campaign_updated is not None
    assert campaign_updated.campaign_name == "Campaign Renamed"

    campaign_map = {"cmp_1": campaign.id}
    adset = meta_sync_service._upsert_adset(
        db,
        account,
        test_org.id,
        {"id": "adset_1", "campaign_id": "cmp_1", "name": "Adset One", "status": "ACTIVE"},
        campaign_map,
    )
    assert adset is not None
    assert adset.campaign_id == campaign.id

    adset_map = {"adset_1": adset.id}
    ad = meta_sync_service._upsert_ad(
        db,
        account,
        test_org.id,
        {
            "id": "ad_1",
            "campaign_id": "cmp_1",
            "adset_id": "adset_1",
            "name": "Ad One",
            "status": "ACTIVE",
        },
        campaign_map,
        adset_map,
    )
    assert ad is not None
    assert ad.ad_name == "Ad One"


@pytest.mark.asyncio
async def test_meta_sync_hierarchy_and_spend_skip_when_no_token(db, test_org, monkeypatch):
    account = _create_ad_account(db, test_org.id)
    monkeypatch.setattr(
        meta_sync_service.meta_token_service,
        "get_token_for_ad_account",
        lambda *_args, **_kwargs: SimpleNamespace(token=None, connection_id=None),
    )

    hierarchy = await meta_sync_service.sync_hierarchy(db, account, full_sync=False)
    assert hierarchy["skipped"] is True
    assert hierarchy["error"] == "no_token"

    spend = await meta_sync_service.sync_spend(
        db,
        account,
        date_start=date.today(),
        date_end=date.today(),
    )
    assert spend["skipped"] is True
    assert spend["error"] == "no_token"


@pytest.mark.asyncio
async def test_meta_sync_forms_no_page_mapping_and_success_path(db, test_org, monkeypatch):
    no_pages = await meta_sync_service.sync_forms(db, test_org.id)
    assert no_pages["error"] == "No active page mappings found"

    page = MetaPageMapping(
        organization_id=test_org.id,
        page_id="page_1",
        is_active=True,
    )
    db.add(page)
    db.commit()

    monkeypatch.setattr(
        meta_sync_service.meta_token_service,
        "get_token_for_page",
        lambda *_args, **_kwargs: SimpleNamespace(token="token-1", connection_id=None),
    )

    async def _fake_fetch_page_forms(page_id: str, access_token: str):
        assert page_id == "page_1"
        assert access_token == "token-1"
        return (
            [
                {
                    "id": "form_1",
                    "name": "Lead Form",
                    "questions": [{"key": "full_name", "label": "Full Name"}],
                }
            ],
            None,
        )

    monkeypatch.setattr(
        meta_sync_service.meta_api, "fetch_page_leadgen_forms", _fake_fetch_page_forms
    )

    synced = await meta_sync_service.sync_forms(db, test_org.id, page_id="page_1")
    assert synced["error"] is None
    assert synced["forms_synced"] == 1
    assert synced["versions_created"] == 1
    db.refresh(page)
    assert page.forms_synced_at is not None


def test_record_sync_error_truncates_and_updates_timestamps(db, test_org):
    account = _create_ad_account(db, test_org.id)
    long_error = "x" * 900
    meta_sync_service._record_sync_error(db, account, long_error)
    db.refresh(account)
    assert account.last_error is not None
    assert len(account.last_error) <= 500
    assert account.last_error_at is not None
    assert account.last_error_at <= datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_meta_sync_hierarchy_and_spend_success_paths(db, test_org, monkeypatch):
    account = _create_ad_account(db, test_org.id)
    monkeypatch.setattr(
        meta_sync_service.meta_token_service,
        "get_token_for_ad_account",
        lambda *_args, **_kwargs: SimpleNamespace(token="token-1", connection_id=None),
    )

    async def _campaigns(*_args, **_kwargs):
        return ([{"id": "camp_1", "name": "C1", "status": "ACTIVE"}], None)

    async def _adsets(*_args, **_kwargs):
        return (
            [{"id": "adset_1", "campaign_id": "camp_1", "name": "A1", "status": "ACTIVE"}],
            None,
        )

    async def _ads(*_args, **_kwargs):
        return (
            [{"id": "ad_1", "campaign_id": "camp_1", "adset_id": "adset_1", "name": "AD1"}],
            None,
        )

    async def _insights(*_args, **kwargs):
        return (
            [
                {
                    "campaign_id": "camp_1",
                    "campaign_name": "C1",
                    "date_start": "2026-01-01",
                    "spend": "10.50",
                    "impressions": "100",
                    "reach": "80",
                    "clicks": "7",
                    "actions": [{"action_type": "lead", "value": "2"}],
                    **(
                        {"publisher_platform": "facebook"}
                        if kwargs.get("breakdowns") == ["publisher_platform"]
                        else {}
                    ),
                }
            ],
            None,
        )

    monkeypatch.setattr(meta_sync_service.meta_api, "fetch_campaigns", _campaigns)
    monkeypatch.setattr(meta_sync_service.meta_api, "fetch_adsets", _adsets)
    monkeypatch.setattr(meta_sync_service.meta_api, "fetch_ads", _ads)
    monkeypatch.setattr(meta_sync_service.meta_api, "fetch_ad_account_insights", _insights)

    hierarchy = await meta_sync_service.sync_hierarchy(db, account, full_sync=False)
    assert hierarchy["error"] is None
    assert hierarchy["campaigns"] == 1
    assert hierarchy["adsets"] == 1
    assert hierarchy["ads"] == 1

    spend = await meta_sync_service.sync_spend(
        db=db,
        ad_account=account,
        date_start=date(2026, 1, 1),
        date_end=date(2026, 1, 2),
        breakdowns=["_total", "publisher_platform"],
    )
    assert spend["error"] is None
    assert spend["rows_synced"] >= 2
    assert spend["campaigns"] == 1


@pytest.mark.asyncio
async def test_meta_sync_forms_error_and_no_token_paths(db, test_org, monkeypatch):
    page = MetaPageMapping(
        organization_id=test_org.id,
        page_id="page_error",
        is_active=True,
    )
    db.add(page)
    db.commit()

    monkeypatch.setattr(
        meta_sync_service.meta_token_service,
        "get_token_for_page",
        lambda *_args, **_kwargs: SimpleNamespace(token=None, connection_id=None),
    )
    result = await meta_sync_service.sync_forms(db, test_org.id, page_id="page_error")
    assert result["forms_synced"] == 0
    db.refresh(page)
    assert page.last_error == "Page token unavailable"

    monkeypatch.setattr(
        meta_sync_service.meta_token_service,
        "get_token_for_page",
        lambda *_args, **_kwargs: SimpleNamespace(token="token-1", connection_id=None),
    )

    async def _fetch_page_error(*_args, **_kwargs):
        return (None, "boom")

    monkeypatch.setattr(meta_sync_service.meta_api, "fetch_page_leadgen_forms", _fetch_page_error)
    result = await meta_sync_service.sync_forms(db, test_org.id, page_id="page_error")
    assert result["forms_synced"] == 0
    db.refresh(page)
    assert page.last_error == "boom"


def test_meta_sync_link_surrogates_and_upsert_rows(db, test_org, test_user, default_stage):
    account = _create_ad_account(db, test_org.id)
    campaign = MetaCampaign(
        organization_id=test_org.id,
        ad_account_id=account.id,
        campaign_external_id="camp_10",
        campaign_name="C10",
        status="ACTIVE",
    )
    db.add(campaign)
    db.flush()

    adset = meta_sync_service._upsert_adset(
        db,
        account,
        test_org.id,
        {"id": "adset_10", "campaign_id": "camp_10", "name": "Adset 10", "status": "ACTIVE"},
        {"camp_10": campaign.id},
    )
    assert adset is not None

    _ = meta_sync_service._upsert_ad(
        db,
        account,
        test_org.id,
        {
            "id": "ad_10",
            "campaign_id": "camp_10",
            "adset_id": "adset_10",
            "name": "Ad 10",
        },
        {"camp_10": campaign.id},
        {"adset_10": adset.id},
    )

    surrogate = Surrogate(
        id=uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid4().int % 90000 + 10000:05d}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type="user",
        owner_id=test_user.id,
        created_by_user_id=test_user.id,
        full_name="Meta Lead",
        email="meta@example.com",
        email_hash="hash-meta",
        meta_ad_external_id="ad_10",
    )
    db.add(surrogate)
    db.commit()

    updated = meta_sync_service.link_surrogates_to_campaigns(db, test_org.id)
    assert updated == 1
    db.refresh(surrogate)
    assert surrogate.meta_campaign_external_id == "camp_10"
    assert surrogate.meta_adset_external_id == "adset_10"

    spend_row = meta_sync_service._upsert_spend_row(
        db,
        account,
        test_org.id,
        {
            "campaign_id": "camp_10",
            "campaign_name": "C10",
            "date_start": "2026-01-01",
            "spend": "15.25",
            "impressions": "200",
            "reach": "150",
            "clicks": "11",
            "actions": [{"action_type": "leadgen", "value": "3"}],
        },
        "_total",
    )
    assert spend_row is not None
    assert spend_row.spend == Decimal("15.25")
    assert spend_row.leads == 3

    platform_row = meta_sync_service._upsert_ad_platform_row(
        db,
        account,
        test_org.id,
        {
            "ad_id": "ad_10",
            "date_start": "2026-01-01",
            "publisher_platform": "facebook",
            "spend": "9.20",
            "impressions": "90",
            "clicks": "5",
            "actions": [{"action_type": "lead", "value": "1"}],
        },
    )
    assert isinstance(platform_row, MetaAdPlatformDaily)
    assert platform_row.platform == "facebook"

    assert (
        meta_sync_service._upsert_spend_row(
            db,
            account,
            test_org.id,
            {"campaign_id": "camp_10", "date_start": "bad-date"},
            "_total",
        )
        is None
    )
    assert (
        meta_sync_service._upsert_ad_platform_row(
            db,
            account,
            test_org.id,
            {"ad_id": None, "date_start": "2026-01-01", "publisher_platform": "facebook"},
        )
        is None
    )


@pytest.mark.asyncio
async def test_meta_sync_ad_platform_and_schedule_branches(db, test_org, monkeypatch):
    account = _create_ad_account(db, test_org.id)
    monkeypatch.setattr(
        meta_sync_service.meta_token_service,
        "get_token_for_ad_account",
        lambda *_args, **_kwargs: SimpleNamespace(token=None, connection_id=None),
    )
    skipped = await meta_sync_service.sync_ad_platform_breakdown(
        db, account, date(2026, 1, 1), date(2026, 1, 2)
    )
    assert skipped["skipped"] is True

    monkeypatch.setattr(
        meta_sync_service.meta_token_service,
        "get_token_for_ad_account",
        lambda *_args, **_kwargs: SimpleNamespace(token="token-1", connection_id=None),
    )

    async def _platform_insights(*_args, **_kwargs):
        return (
            [
                {
                    "ad_id": "ad_20",
                    "ad_name": "Ad 20",
                    "date_start": "2026-01-01",
                    "publisher_platform": "facebook",
                    "spend": "5.00",
                    "impressions": "50",
                    "clicks": "4",
                    "actions": [{"action_type": "lead", "value": "1"}],
                }
            ],
            None,
        )

    monkeypatch.setattr(meta_sync_service.meta_api, "fetch_ad_account_insights", _platform_insights)
    monkeypatch.setattr(
        "app.services.meta_lead_service.backfill_platform_for_date_range",
        lambda *_args, **_kwargs: 1,
    )
    synced = await meta_sync_service.sync_ad_platform_breakdown(
        db, account, date(2026, 1, 1), date(2026, 1, 2)
    )
    assert synced["error"] is None
    assert synced["rows_synced"] == 1

    captured_ranges: list[tuple[date, date]] = []

    async def _capture_sync(*_args, **kwargs):
        if "date_start" in kwargs:
            captured_ranges.append((kwargs["date_start"], kwargs["date_end"]))
        else:
            captured_ranges.append((_args[2], _args[3]))
        return {"rows_synced": 0, "campaigns": 0, "error": None, "skipped": False}

    monkeypatch.setattr(meta_sync_service, "sync_spend", _capture_sync)
    monkeypatch.setattr(meta_sync_service, "date", SimpleNamespace(today=lambda: date(2026, 1, 11)))
    account.spend_synced_at = None
    await meta_sync_service.run_spend_sync_schedule(db, account)
    assert captured_ranges[-1] == (date(2025, 7, 15), date(2026, 1, 10))

    account.spend_synced_at = datetime.now(timezone.utc)
    await meta_sync_service.run_spend_sync_schedule(db, account)
    assert captured_ranges[-1] == (date(2025, 10, 13), date(2026, 1, 10))

    monkeypatch.setattr(meta_sync_service, "date", SimpleNamespace(today=lambda: date(2026, 1, 12)))
    await meta_sync_service.run_spend_sync_schedule(db, account)
    assert captured_ranges[-1] == (date(2026, 1, 5), date(2026, 1, 11))


def test_meta_sync_forms_upsert_and_account_listing(db, test_org):
    form, created = meta_sync_service._upsert_form(
        db,
        test_org.id,
        "page_1",
        {"id": "form_1", "name": "Lead Form", "questions": [{"key": "email"}]},
    )
    assert isinstance(form, MetaForm)
    assert created is True

    form_again, created_again = meta_sync_service._upsert_form(
        db,
        test_org.id,
        "page_1",
        {"id": "form_1", "name": "Lead Form", "questions": [{"key": "email"}]},
    )
    assert form_again is not None
    assert created_again is False

    missing_form, missing_created = meta_sync_service._upsert_form(
        db,
        test_org.id,
        "page_1",
        {"name": "No ID"},
    )
    assert missing_form is None
    assert missing_created is False

    account_active = _create_ad_account(db, test_org.id)
    account_inactive = _create_ad_account(db, test_org.id)
    account_inactive.is_active = False
    db.commit()

    all_active = meta_sync_service.get_active_ad_accounts(db)
    assert any(a.id == account_active.id for a in all_active)
    assert all(a.is_active for a in all_active)

    org_active = meta_sync_service.get_active_ad_accounts(db, org_id=test_org.id)
    assert all(a.organization_id == test_org.id for a in org_active)


@pytest.mark.asyncio
async def test_meta_api_helpers_and_http_error_paths(monkeypatch):
    monkeypatch.setattr(meta_api.settings, "META_APP_SECRET", "secret")
    payload = b"payload"
    sig = "sha256=" + meta_api.hmac.new(b"secret", payload, meta_api.hashlib.sha256).hexdigest()
    assert meta_api.verify_signature(payload, sig) is True
    assert meta_api.verify_signature(payload, "bad") is False
    assert meta_api.compute_appsecret_proof("token")

    normalized = meta_api.normalize_field_data(
        [
            {"name": "Phone Number", "values": ["+15550001111"]},
            {"name": "first_name", "values": ["Jane"]},
            {"name": "last_name", "values": ["Doe"]},
            {"name": "e-mail", "values": ["jane@example.com"]},
            {"name": "state", "values": ["CA"]},
        ]
    )
    assert normalized["phone"] == "+15550001111"
    assert normalized["full_name"] == "Jane Doe"
    assert normalized["email"] == "jane@example.com"
    assert normalized["state"] == "CA"

    assert meta_api.parse_meta_timestamp("2026-01-10T12:00:00+0000") is not None
    assert meta_api.parse_meta_timestamp("2026-01-10T12:00:00") is not None
    assert meta_api.parse_meta_timestamp("bad") is None

    raw = meta_api.extract_field_data_raw(
        [{"name": "Hobbies", "values": ["a", "b"]}, {"name": "Email", "values": ["x@example.com"]}]
    )
    assert raw["hobbies"] == ["a", "b"]
    assert raw["email"] == "x@example.com"

    monkeypatch.setattr(meta_api.settings, "META_TEST_MODE", False)
    monkeypatch.setattr(
        meta_api.httpx,
        "AsyncClient",
        lambda **_kwargs: _FakeAsyncClient(responses=[_FakeResponse(500, text="boom")]),
    )
    data, error = await meta_api.fetch_lead_details("lead_1", "token-1")
    assert data is None
    assert "Meta API 500" in (error or "")

    monkeypatch.setattr(
        meta_api.httpx,
        "AsyncClient",
        lambda **_kwargs: _FakeAsyncClient(error=meta_api.httpx.TimeoutException("timeout")),
    )
    data, error = await meta_api.fetch_lead_details("lead_1", "token-1")
    assert data is None
    assert error == "Meta API timeout"

    monkeypatch.setattr(meta_api.settings, "META_TEST_MODE", True)
    insights, err = await meta_api.fetch_ad_account_insights(
        "act_1",
        "token-1",
        date_start="2026-01-01",
        date_end="2026-01-02",
        breakdowns=["region"],
    )
    assert err is None
    assert insights

    campaigns, err = await meta_api.fetch_campaigns("act_1", "token-1")
    assert err is None
    assert campaigns

    forms, err = await meta_api.fetch_page_leadgen_forms("page_1", "token-1")
    assert err is None
    assert forms

    monkeypatch.setattr(meta_api.settings, "META_TEST_MODE", False)
    empty, err = await meta_api.fetch_campaigns("", "")
    assert empty is None
    assert err == "No access token provided"
