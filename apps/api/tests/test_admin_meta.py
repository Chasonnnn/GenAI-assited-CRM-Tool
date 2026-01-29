"""
Tests for Meta admin endpoints after OAuth cutover.

Manual token management is disabled; list endpoints remain.
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_meta_pages_empty(authed_client: AsyncClient):
    response = await authed_client.get("/admin/meta-pages")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_meta_page_disabled(authed_client: AsyncClient):
    response = await authed_client.post(
        "/admin/meta-pages",
        json={"page_id": "123456789", "access_token": "EAAtest"},
    )
    assert response.status_code == 410
    assert "oauth" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_meta_page_disabled(authed_client: AsyncClient):
    response = await authed_client.put(
        "/admin/meta-pages/123456789",
        json={"page_name": "Updated"},
    )
    assert response.status_code == 410
    assert "oauth" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_meta_page_disabled(authed_client: AsyncClient):
    response = await authed_client.delete("/admin/meta-pages/123456789")
    assert response.status_code == 410
    assert "oauth" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_meta_pages_scoped_to_org(authed_client: AsyncClient, db, test_org):
    from app.db.enums import Role
    from app.db.models import Membership, MetaPageMapping, Organization, User

    org2 = Organization(
        id=uuid.uuid4(),
        name="Org 2",
        slug=f"org2-{uuid.uuid4().hex[:8]}",
    )
    db.add(org2)

    user2 = User(
        id=uuid.uuid4(),
        email=f"user2-{uuid.uuid4().hex[:8]}@test.com",
        display_name="User 2",
        token_version=1,
    )
    db.add(user2)
    db.flush()

    membership2 = Membership(
        id=uuid.uuid4(),
        user_id=user2.id,
        organization_id=org2.id,
        role=Role.ADMIN,
    )
    db.add(membership2)
    db.flush()

    page_org1 = MetaPageMapping(
        organization_id=test_org.id,
        page_id="org1page",
        page_name="Org 1 Page",
        access_token_encrypted="enc_org1",
        is_active=True,
    )
    page_org2 = MetaPageMapping(
        organization_id=org2.id,
        page_id="org2page",
        page_name="Org 2 Page",
        access_token_encrypted="enc_org2",
        is_active=True,
    )
    db.add_all([page_org1, page_org2])
    db.commit()

    response = await authed_client.get("/admin/meta-pages")
    assert response.status_code == 200
    data = response.json()

    page_ids = {p["page_id"] for p in data}
    assert "org1page" in page_ids
    assert "org2page" not in page_ids


@pytest.mark.asyncio
async def test_create_meta_ad_account_disabled(authed_client: AsyncClient):
    response = await authed_client.post(
        "/admin/meta-ad-accounts",
        json={"ad_account_external_id": "act_123", "ad_account_name": "Test"},
    )
    assert response.status_code == 410
    assert "oauth" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_meta_ad_account_disabled(authed_client: AsyncClient, db, test_org):
    from app.db.models import MetaAdAccount

    account = MetaAdAccount(
        organization_id=test_org.id,
        ad_account_external_id="act_123",
        ad_account_name="Account",
        is_active=True,
    )
    db.add(account)
    db.commit()

    response = await authed_client.put(
        f"/admin/meta-ad-accounts/{account.id}",
        json={"ad_account_name": "Updated", "capi_enabled": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ad_account_name"] == "Updated"
    assert data["capi_enabled"] is True


@pytest.mark.asyncio
async def test_delete_meta_ad_account_disabled(authed_client: AsyncClient, db, test_org):
    from app.db.models import MetaAdAccount

    account = MetaAdAccount(
        organization_id=test_org.id,
        ad_account_external_id="act_999",
        ad_account_name="Account",
        is_active=True,
    )
    db.add(account)
    db.commit()

    response = await authed_client.delete(f"/admin/meta-ad-accounts/{account.id}")
    assert response.status_code == 204
    db.refresh(account)
    assert account.is_active is False
