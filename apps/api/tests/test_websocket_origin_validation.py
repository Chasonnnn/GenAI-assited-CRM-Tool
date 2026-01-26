def test_validate_websocket_origin_allows_org_domain(db, test_org, monkeypatch):
    from app.core.config import settings
    from app.routers import websocket as websocket_router

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    test_org.slug = "ewi"
    db.commit()

    assert websocket_router.validate_websocket_origin("https://ewi.surrogacyforce.com", db) is True


def test_validate_websocket_origin_rejects_unknown_domain(db, test_org, monkeypatch):
    from app.core.config import settings
    from app.routers import websocket as websocket_router

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    test_org.slug = "ewi"
    db.commit()

    assert websocket_router.validate_websocket_origin("https://evil.com", db) is False


def test_validate_websocket_origin_rejects_missing_host(db):
    from app.routers import websocket as websocket_router

    assert websocket_router.validate_websocket_origin("not-a-url", db) is False
