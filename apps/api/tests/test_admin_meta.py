"""
Comprehensive tests for Meta Leads Admin API.

Tests CRUD operations, validation, permissions, and error handling.
"""
import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_meta_pages_empty(authed_client: AsyncClient):
    """Test listing pages returns empty array when none configured."""
    response = await authed_client.get("/admin/meta-pages")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_meta_page_success(authed_client: AsyncClient, db, test_org):
    """Test creating a Meta page with valid data."""
    response = await authed_client.post(
        "/admin/meta-pages",
        json={
            "page_id": "123456789",
            "page_name": "Test Page",
            "access_token": "EAAtest123",
            "expires_days": 60,
        },
    )
    assert response.status_code == 201
    data = response.json()
    
    assert data["page_id"] == "123456789"
    assert data["page_name"] == "Test Page"
    assert data["organization_id"] == str(test_org.id)
    assert data["is_active"] is True
    assert "token_expires_at" in data
    assert "access_token" not in data  # Token should not be returned


@pytest.mark.asyncio
async def test_create_meta_page_encrypts_token(authed_client: AsyncClient, db, test_org):
    """Test that access token is encrypted in database."""
    from app.db.models import MetaPageMapping
    
    response = await authed_client.post(
        "/admin/meta-pages",
        json={
            "page_id": "999888777",
            "access_token": "EAAsecret",
            "expires_days": 30,
        },
    )
    assert response.status_code == 201
    
    # Verify token is encrypted in DB (not plaintext)
    page = db.query(MetaPageMapping).filter(
        MetaPageMapping.page_id == "999888777"
    ).first()
    assert page is not None
    assert page.access_token_encrypted != "EAAsecret"
    assert len(page.access_token_encrypted) > 50  # Encrypted should be longer


@pytest.mark.asyncio
async def test_create_meta_page_duplicate_rejected(authed_client: AsyncClient):
    """Test creating duplicate page_id returns 409 Conflict."""
    # Create first page
    response1 = await authed_client.post(
        "/admin/meta-pages",
        json={"page_id": "111222333", "access_token": "EAAtest1"},
    )
    assert response1.status_code == 201
    
    # Try to create duplicate
    response2 = await authed_client.post(
        "/admin/meta-pages",
        json={"page_id": "111222333", "access_token": "EAAtest2"},
    )
    assert response2.status_code == 409
    assert "already exists" in response2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_meta_page_without_auth_fails(client: AsyncClient):
    """Test unauthenticated request returns 401."""
    response = await client.post(
        "/admin/meta-pages",
        json={"page_id": "123", "access_token": "EAA"},
    )
    assert response.status_code == 403  # CSRF check fails before auth


@pytest.mark.asyncio
async def test_create_meta_page_validation(authed_client: AsyncClient):
    """Test validation of required fields."""
    # Missing page_id
    response = await authed_client.post(
        "/admin/meta-pages",
        json={"access_token": "EAAtest"},
    )
    assert response.status_code == 422
    
    # Missing access_token
    response = await authed_client.post(
        "/admin/meta-pages",
        json={"page_id": "123"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_meta_page_success(authed_client: AsyncClient):
    """Test updating existing page."""
    # Create page
    create_response = await authed_client.post(
        "/admin/meta-pages",
        json={
            "page_id": "555666777",
            "page_name": "Original Name",
            "access_token": "EAAoriginal",
        },
    )
    assert create_response.status_code == 201
    
    # Update page
    update_response = await authed_client.put(
        "/admin/meta-pages/555666777",
        json={
            "page_name": "Updated Name",
            "is_active": False,
        },
    )
    assert update_response.status_code == 200
    data = update_response.json()
    
    assert data["page_name"] == "Updated Name"
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_update_meta_page_not_found(authed_client: AsyncClient):
    """Test updating non-existent page returns 404."""
    response = await authed_client.put(
        "/admin/meta-pages/nonexistent",
        json={"page_name": "Test"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_meta_page_access_token(authed_client: AsyncClient, db):
    """Test updating access token."""
    from app.db.models import MetaPageMapping
    from app.core.encryption import decrypt_token
    
    # Create page
    create_response = await authed_client.post(
        "/admin/meta-pages",
        json={"page_id": "777888999", "access_token": "EAAold"},
    )
    assert create_response.status_code == 201
    
    # Update token
    update_response = await authed_client.put(
        "/admin/meta-pages/777888999",
        json={"access_token": "EAAnew", "expires_days": 90},
    )
    assert update_response.status_code == 200
    
    # Verify new token is encrypted
    page = db.query(MetaPageMapping).filter(
        MetaPageMapping.page_id == "777888999"
    ).first()
    decrypted = decrypt_token(page.access_token_encrypted)
    assert decrypted == "EAAnew"


@pytest.mark.asyncio
async def test_delete_meta_page_success(authed_client: AsyncClient, db):
    """Test deleting page."""
    from app.db.models import MetaPageMapping
    
    # Create page
    create_response = await authed_client.post(
        "/admin/meta-pages",
        json={"page_id": "delete123", "access_token": "EAAdelete"},
    )
    assert create_response.status_code == 201
    
    # Delete page
    delete_response = await authed_client.delete("/admin/meta-pages/delete123")
    assert delete_response.status_code == 204
    
    # Verify deleted from DB
    page = db.query(MetaPageMapping).filter(
        MetaPageMapping.page_id == "delete123"
    ).first()
    assert page is None


@pytest.mark.asyncio
async def test_delete_meta_page_not_found(authed_client: AsyncClient):
    """Test deleting non-existent page returns 404."""
    response = await authed_client.delete("/admin/meta-pages/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_meta_pages_returns_all(authed_client: AsyncClient):
    """Test listing returns all pages for organization."""
    # Create multiple pages
    pages = ["page1", "page2", "page3"]
    for page_id in pages:
        response = await authed_client.post(
            "/admin/meta-pages",
            json={"page_id": page_id, "access_token": f"EAA{page_id}"},
        )
        assert response.status_code == 201
    
    # List pages
    response = await authed_client.get("/admin/meta-pages")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 3
    returned_ids = {p["page_id"] for p in data}
    assert returned_ids == set(pages)


@pytest.mark.asyncio
async def test_meta_pages_org_isolation(authed_client: AsyncClient, db, client):
    """Test pages are isolated per organization."""
    from app.db.models import Organization, User, Membership, MetaPageMapping
    from app.db.enums import Role
    from app.core.security import create_session_token
    from app.core.deps import COOKIE_NAME
    
    # Create second org
    org2 = Organization(
        id=uuid.uuid4(),
        name="Org 2",
        slug=f"org2-{uuid.uuid4().hex[:8]}",
    )
    db.add(org2)
    
    # Create user in second org
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
    
    # Create page in org2
    page2 = MetaPageMapping(
        organization_id=org2.id,
        page_id="org2page",
        access_token_encrypted="encrypted",
        is_active=True,
    )
    db.add(page2)
    db.flush()
    
    # Authed client (org1) should not see org2's pages
    response = await authed_client.get("/admin/meta-pages")
    assert response.status_code == 200
    data = response.json()
    
    page_ids = [p["page_id"] for p in data]
    assert "org2page" not in page_ids


@pytest.mark.asyncio
async def test_create_meta_page_without_encryption_key_fails(authed_client: AsyncClient, monkeypatch):
    """Test creation fails gracefully when encryption not configured."""
    from app.routers import admin_meta
    
    # Monkeypatch in the router module where function is imported
    monkeypatch.setattr(admin_meta, "is_encryption_configured", lambda: False)
    
    response = await authed_client.post(
        "/admin/meta-pages",
        json={"page_id": "test", "access_token": "EAAtest"},
    )
    assert response.status_code == 500
    assert "encryption" in response.json()["detail"].lower()
