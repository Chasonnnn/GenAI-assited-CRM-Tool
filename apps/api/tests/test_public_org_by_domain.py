import pytest


@pytest.mark.asyncio
async def test_public_org_by_domain_case_insensitive(client, db, test_org, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    test_org.slug = "ewi"
    db.commit()

    response = await client.get("/public/org-by-domain?domain=EWI.surrogacyforce.com")
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "ewi"
    assert data["portal_base_url"] == "https://ewi.surrogacyforce.com"
    assert response.headers.get("cache-control") == "public, max-age=60"


@pytest.mark.asyncio
async def test_public_org_by_domain_returns_404_for_old_slug(client, db, test_org, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PLATFORM_BASE_DOMAIN", "surrogacyforce.com", raising=False)
    test_org.slug = "old"
    db.commit()

    test_org.slug = "new"
    db.commit()

    response = await client.get("/public/org-by-domain?domain=old.surrogacyforce.com")
    assert response.status_code == 404
