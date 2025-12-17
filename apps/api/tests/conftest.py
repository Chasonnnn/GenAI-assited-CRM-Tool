import asyncio
from typing import AsyncGenerator, Generator

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session

from app.main import app
from app.db.session import engine, SessionLocal
from app.core.deps import get_db

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
