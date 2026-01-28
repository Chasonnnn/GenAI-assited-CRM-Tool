from datetime import datetime, timezone
from uuid import uuid4


def test_analytics_service_delegates_surrogate_summary(monkeypatch):
    from app.services import analytics_service, analytics_surrogate_service

    sentinel = {"ok": True}

    def fake_get_cached_analytics_summary(db, organization_id, start, end):
        assert organization_id is not None
        assert start.tzinfo is not None
        assert end.tzinfo is not None
        return sentinel

    monkeypatch.setattr(
        analytics_surrogate_service,
        "get_cached_analytics_summary",
        fake_get_cached_analytics_summary,
    )

    result = analytics_service.get_cached_analytics_summary(
        db=object(),
        organization_id=uuid4(),
        start=datetime.now(timezone.utc),
        end=datetime.now(timezone.utc),
    )

    assert result is sentinel


def test_analytics_service_delegates_meta_accounts(monkeypatch):
    from app.services import analytics_meta_service, analytics_service

    sentinel = [{"id": "account"}]

    def fake_get_meta_ad_accounts(db, organization_id):
        assert organization_id is not None
        return sentinel

    monkeypatch.setattr(analytics_meta_service, "get_meta_ad_accounts", fake_get_meta_ad_accounts)

    result = analytics_service.get_meta_ad_accounts(db=object(), organization_id=uuid4())

    assert result is sentinel


def test_analytics_service_delegates_activity_feed(monkeypatch):
    from app.services import analytics_service, analytics_usage_service

    sentinel = ([{"id": "activity"}], True)

    def fake_get_activity_feed(
        db, organization_id, limit=20, offset=0, activity_type=None, user_id=None
    ):
        assert limit == 20
        assert offset == 0
        return sentinel

    monkeypatch.setattr(analytics_usage_service, "get_activity_feed", fake_get_activity_feed)

    result = analytics_service.get_activity_feed(db=object(), organization_id=uuid4())

    assert result == sentinel
