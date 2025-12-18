"""
Test configuration and fixtures.

Provides:
- Database session with savepoint (rollback after each test)
- JWT token minting for authenticated tests
- HTTPX AsyncClient with proper headers
"""
import asyncio
import os
import uuid
from typing import AsyncGenerator, Generator
from dataclasses import dataclass

import pytest

# Set test environment variables BEFORE any app imports
os.environ.setdefault("DEV_BYPASS_AUTH", "False")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("FERNET_KEY", "_uKVT313or8juloqHLg9OtBNJv9LCBzEC6mJ1yG9S_E=")
os.environ.setdefault("ZOOM_CLIENT_ID", "test-zoom-client-id")
os.environ.setdefault("ZOOM_CLIENT_SECRET", "test-zoom-client-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")


# =============================================================================
# Configuration
# =============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for each test session."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def db_engine():
    """Yields the SQLAlchemy engine."""
    from app.db.session import engine
    yield engine


@pytest.fixture(scope="function")
def db(db_engine) -> Generator:
    """
    Creates a database session for tests.
    """
    from sqlalchemy import event
    from app.db.session import SessionLocal
    
    connection = db_engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)

    # Start a SAVEPOINT so application code can call session.commit()
    # without committing the outer test transaction.
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(session_, transaction_):  # type: ignore[no-redef]
        parent = getattr(transaction_, "_parent", None)
        if transaction_.nested and parent is not None and not parent.nested:
            session_.begin_nested()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


# =============================================================================
# Entity Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def test_org(db):
    """Create a test organization."""
    from app.db.models import Organization
    
    org = Organization(
        id=uuid.uuid4(),
        name="Test Organization",
        slug=f"test-org-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(org)
    db.flush()
    return org


@pytest.fixture(scope="function")
def test_user(db, test_org):
    """Create a test user with membership in test_org."""
    from app.db.models import User, Membership
    from app.db.enums import Role
    
    user = User(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Test User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    
    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=test_org.id,
        role=Role.DEVELOPER,
    )
    db.add(membership)
    db.flush()
    
    return user


# =============================================================================
# Auth Fixtures
# =============================================================================

@dataclass
class TestAuth:
    """Test authentication context."""
    user: object
    org: object
    token: str
    cookie_name: str


@pytest.fixture(scope="function")
def test_auth(test_user, test_org):
    """Create JWT token for test user."""
    from app.core.security import create_session_token
    from app.core.deps import COOKIE_NAME
    from app.db.enums import Role
    
    token = create_session_token(
        user_id=test_user.id,
        org_id=test_org.id,
        role=Role.DEVELOPER.value,
        token_version=test_user.token_version,
    )
    return TestAuth(
        user=test_user,
        org=test_org,
        token=token,
        cookie_name=COOKIE_NAME,
    )


# =============================================================================
# Client Fixtures
# =============================================================================

@pytest.fixture(scope="function")
async def client(db) -> AsyncGenerator:
    """
    Create unauthenticated AsyncClient for testing public endpoints.
    """
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.deps import get_db
    
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app), 
        base_url="http://test"
    ) as c:
        yield c
    
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def authed_client(db, test_auth) -> AsyncGenerator:
    """
    Create authenticated AsyncClient with JWT cookie and CSRF header.
    """
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.deps import get_db
    
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app), 
        base_url="http://test",
        cookies={test_auth.cookie_name: test_auth.token},
        headers={"X-Requested-With": "XMLHttpRequest"},
    ) as c:
        yield c
    
    app.dependency_overrides.clear()
