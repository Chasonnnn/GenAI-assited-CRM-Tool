import pytest
from datetime import date, datetime, timezone


@pytest.mark.asyncio
async def test_sync_ad_platform_breakdown_backfills_leads(db, test_auth, monkeypatch):
    from app.db.models import MetaAdAccount, MetaLead, MetaAdPlatformDaily
    from app.services import meta_sync_service, meta_token_service, meta_api

    # Ensure new table exists in test database
    MetaAdPlatformDaily.__table__.create(db.get_bind(), checkfirst=True)

    # Create ad account
    ad_account = MetaAdAccount(
        organization_id=test_auth.org.id,
        ad_account_external_id="act_123",
        ad_account_name="Test Account",
        is_active=True,
    )
    db.add(ad_account)
    db.flush()

    lead = MetaLead(
        organization_id=test_auth.org.id,
        meta_lead_id="lead_1",
        field_data_raw={"meta_ad_id": "ad_123"},
        field_data={"meta_ad_id": "ad_123"},
        meta_created_time=datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc),
    )
    db.add(lead)
    db.commit()

    async def fake_fetch_ad_account_insights(*args, **kwargs):
        return (
            [
                {
                    "ad_id": "ad_123",
                    "ad_name": "Test Ad",
                    "spend": "12.34",
                    "impressions": "100",
                    "clicks": "5",
                    "actions": [{"action_type": "lead", "value": "2"}],
                    "date_start": "2026-01-10",
                    "publisher_platform": "facebook",
                }
            ],
            None,
        )

    monkeypatch.setattr(meta_api, "fetch_ad_account_insights", fake_fetch_ad_account_insights)
    monkeypatch.setattr(
        meta_token_service,
        "get_token_for_ad_account",
        lambda *args, **kwargs: meta_token_service.TokenResult(
            token="token", connection_id=None, needs_reauth=False
        ),
    )

    result = await meta_sync_service.sync_ad_platform_breakdown(
        db=db,
        ad_account=ad_account,
        date_start=date(2026, 1, 10),
        date_end=date(2026, 1, 10),
    )

    assert result["error"] is None
    assert result["rows_synced"] == 1
    assert result["ads"] == 1

    platform_row = (
        db.query(MetaAdPlatformDaily)
        .filter(
            MetaAdPlatformDaily.organization_id == test_auth.org.id,
            MetaAdPlatformDaily.ad_external_id == "ad_123",
            MetaAdPlatformDaily.spend_date == date(2026, 1, 10),
        )
        .first()
    )
    assert platform_row is not None
    assert platform_row.platform == "facebook"

    db.refresh(lead)
    assert lead.field_data_raw.get("meta_platform") == "facebook"
    assert lead.field_data.get("meta_platform") == "facebook"
