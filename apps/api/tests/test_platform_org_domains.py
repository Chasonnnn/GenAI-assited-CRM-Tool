import uuid

import pytest


async def _create_org(authed_client, db, test_user, monkeypatch, **overrides):
    from app.services import invite_email_service

    if not test_user.is_platform_admin:
        test_user.is_platform_admin = True
        db.commit()

    async def fake_send_invite_email(*_args, **_kwargs):
        return {"success": True}

    monkeypatch.setattr(invite_email_service, "send_invite_email", fake_send_invite_email)

    payload = {
        "name": "Orchid",
        "slug": f"org-{uuid.uuid4().hex[:6]}",
        "timezone": "America/Los_Angeles",
        "admin_email": f"admin-{uuid.uuid4().hex[:6]}@orchid.com",
    }
    payload.update(overrides)
    return await authed_client.post("/platform/orgs", json=payload)


@pytest.mark.asyncio
async def test_platform_create_org_allows_two_char_slug(authed_client, db, test_user, monkeypatch):
    response = await _create_org(
        authed_client,
        db,
        test_user,
        monkeypatch,
        slug="oc",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "oc"
    assert "portal_base_url" in data


@pytest.mark.asyncio
async def test_platform_create_org_rejects_one_char_slug(authed_client, db, test_user, monkeypatch):
    response = await _create_org(
        authed_client,
        db,
        test_user,
        monkeypatch,
        slug="o",
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_platform_create_org_rejects_reserved_slug(authed_client, db, test_user, monkeypatch):
    response = await _create_org(
        authed_client,
        db,
        test_user,
        monkeypatch,
        slug="ops",
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_platform_create_org_rejects_invalid_chars(authed_client, db, test_user, monkeypatch):
    response = await _create_org(
        authed_client,
        db,
        test_user,
        monkeypatch,
        slug="acme!",
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_platform_create_org_normalizes_slug_lowercase(
    authed_client, db, test_user, monkeypatch
):
    response = await _create_org(
        authed_client,
        db,
        test_user,
        monkeypatch,
        slug="EWI",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "ewi"


@pytest.mark.asyncio
async def test_platform_update_org_slug(authed_client, db, test_user, test_org):
    test_user.is_platform_admin = True
    db.commit()

    response = await authed_client.patch(
        f"/platform/orgs/{test_org.id}",
        json={"slug": "ocd"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "ocd"
    assert "portal_base_url" in data


@pytest.mark.asyncio
async def test_platform_update_org_slug_conflict_returns_409(
    authed_client, db, test_user, monkeypatch, test_org
):
    existing = await _create_org(
        authed_client,
        db,
        test_user,
        monkeypatch,
        slug="ocd",
    )
    assert existing.status_code == 200

    response = await authed_client.patch(
        f"/platform/orgs/{test_org.id}",
        json={"slug": "ocd"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_slug_change_audit_logged(authed_client, db, test_user, test_org):
    from app.db.models import AdminActionLog

    test_user.is_platform_admin = True
    db.commit()

    old_slug = test_org.slug
    response = await authed_client.patch(
        f"/platform/orgs/{test_org.id}",
        json={"slug": "ocd"},
    )
    assert response.status_code == 200

    log = (
        db.query(AdminActionLog)
        .filter(
            AdminActionLog.action == "org.update",
            AdminActionLog.target_organization_id == test_org.id,
        )
        .order_by(AdminActionLog.created_at.desc())
        .first()
    )
    assert log is not None
    metadata = log.metadata_ or {}
    assert "slug" in metadata.get("changed_fields", [])
    assert metadata.get("old_slug") == old_slug
    assert metadata.get("new_slug") == "ocd"
