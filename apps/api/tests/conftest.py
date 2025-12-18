import asyncio
import uuid
from typing import AsyncGenerator, Generator
from dataclasses import dataclass
from datetime import datetime

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import engine, SessionLocal
from app.core.deps import get_db, get_current_session
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
# Database Fixtures
# =============================================================================

@pytest.fixture(scope="session", autouse=True)
def db_engine():
    """Yields the SQLAlchemy engine."""
    # In a real scenario, you might want to create a separate test DB here
    # or use a transaction-rollback strategy for every test.
    # For now, we use the existing engine configuration.
    yield engine
    # engine.dispose()


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """
    Creates a fresh database session for a test.
    
    This session should ideally be rolled back after the test 
    to keep the database clean.
    """
    connection = engine.connect()
    # Begin a non-ORM transaction
    transaction = connection.begin()
    
    # Bind an individual Session to the connection
    session = SessionLocal(bind=connection)
    
    yield session
    
    session.close()
    # Rollback the transaction - everything done in the test is undone
    transaction.rollback()
    connection.close()


# =============================================================================
# Client Fixtures
# =============================================================================

@pytest.fixture(scope="function")
async def client(db: Session) -> AsyncGenerator[AsyncClient, None]:
    """
    Create a new FastAPI AsyncClient that overrides the `get_db` dependency.
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


# =============================================================================
# Entity Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def test_org(db: Session) -> Organization:
    """Create a test organization."""
    org = Organization(
        id=uuid.uuid4(),
        name="Test Organization",
        slug=f"test-org-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
        # Note: current_version will use DB default if column exists
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
        google_sub=f"google-{uuid.uuid4().hex}",
    )
    db.add(user)
    db.flush()
    
    # Add membership
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
class MockSession:
    """Mock session for testing authenticated endpoints."""
    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str
    email: str


@pytest.fixture(scope="function")
def mock_session(test_user: User, test_org: Organization) -> MockSession:
    """Create a mock session for the test user."""
    return MockSession(
        user_id=test_user.id,
        org_id=test_org.id,
        role=Role.DEVELOPER.value,
        email=test_user.email,
    )


@pytest.fixture(scope="function")
async def authed_client(
    db: Session, 
    mock_session: MockSession
) -> AsyncGenerator[AsyncClient, None]:
    """
    Create an authenticated AsyncClient with session mocked.
    """
    def override_get_db():
        yield db
    
    def override_get_session():
        return mock_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_session] = override_get_session
    
    async with AsyncClient(
        transport=ASGITransport(app=app), 
        base_url="http://test",
        headers={"X-CSRF-Token": "test-csrf-token"}  # Include CSRF for POST/PATCH
    ) as c:
        yield c
    
    app.dependency_overrides.clear()
