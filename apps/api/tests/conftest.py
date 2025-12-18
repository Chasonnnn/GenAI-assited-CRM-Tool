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
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session

# Ensure DEV_BYPASS_AUTH is disabled for tests
os.environ["DEV_BYPASS_AUTH"] = "False"

from app.main import app
from app.db.session import engine, SessionLocal
from app.core.deps import get_db, COOKIE_NAME
from app.core.security import create_session_token
from app.db.models import Organization, User, Membership
from app.db.enums import Role


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
# Database Fixtures (Savepoint pattern)
# =============================================================================

@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """
    Creates a database session with savepoint for test isolation.
    
    Uses nested savepoints so that app code can call commit()
    without ending the test transaction.
    """
    connection = engine.connect()
    # Begin outer transaction that we'll rollback at end
    transaction = connection.begin()
    
    # Create session bound to this connection
    session = SessionLocal(bind=connection)
    
    # Start a SAVEPOINT
    nested = connection.begin_nested()
    
    # Listen for commit() calls to restart the savepoint
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, trans):
        nonlocal nested
        if trans.nested and not trans._parent.nested:
            # Create new savepoint after each commit
            nested = connection.begin_nested()
    
    yield session
    
    session.close()
    # Rollback outer transaction - undoes all test changes
    transaction.rollback()
    connection.close()


# Import event listener after to avoid circular import issues
from sqlalchemy import event


@pytest.fixture(scope="function")
def test_org(db: Session) -> Organization:
    """Create a test organization."""
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
def test_user(db: Session, test_org: Organization) -> User:
    """Create a test user with membership in test_org."""
    user = User(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4().hex[:8]}@test.com",
        display_name="Test User",
    )
    db.add(user)
    db.flush()
    
    # Add membership as developer
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
    user: User
    org: Organization
    token: str
    cookie_name: str = COOKIE_NAME


@pytest.fixture(scope="function")
def test_auth(test_user: User, test_org: Organization) -> TestAuth:
    """Create JWT token for test user."""
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
    )


# =============================================================================
# Client Fixtures
# =============================================================================

@pytest.fixture(scope="function")
async def client(db: Session) -> AsyncGenerator[AsyncClient, None]:
    """
    Create unauthenticated AsyncClient for testing public endpoints.
    """
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
async def authed_client(
    db: Session, 
    test_auth: TestAuth
) -> AsyncGenerator[AsyncClient, None]:
    """
    Create authenticated AsyncClient with JWT cookie and CSRF header.
    """
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=app), 
        base_url="http://test",
        cookies={test_auth.cookie_name: test_auth.token},
        headers={"X-Requested-With": "XMLHttpRequest"},  # CSRF header
    ) as c:
        yield c
    
    app.dependency_overrides.clear()
