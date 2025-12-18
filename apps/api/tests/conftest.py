"""
Test configuration and fixtures.

NOTE ON INTEGRATION TESTS:
The following issues make integration testing complex:
1. require_roles() calls get_current_session() directly, not via Depends
2. DEV_BYPASS_AUTH=True in deps.py bypasses authentication  
3. DB transaction fixture gets committed by app code

For proper integration tests, need:
- Real JWT tokens via create_session_token()
- Monkeypatching app.core.deps.get_current_session
- Nested transaction/savepoint pattern for DB
- DEV_BYPASS_AUTH=False in test environment

Current tests focus on unit tests that don't require these complex patterns.
"""
import asyncio
from typing import Generator

import pytest
from sqlalchemy.orm import Session

from app.db.session import engine, SessionLocal


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
# Database Fixtures (for future integration tests)
# =============================================================================

@pytest.fixture(scope="session", autouse=True)
def db_engine():
    """Yields the SQLAlchemy engine."""
    yield engine


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """
    Creates a fresh database session for a test.
    
    NOTE: This simple fixture won't work for integration tests because
    app code calls db.commit() which commits the transaction.
    For integration tests, use nested transaction/savepoint pattern.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    
    yield session
    
    session.close()
    try:
        transaction.rollback()
    except Exception:
        pass  # Transaction may already be committed by app code
    connection.close()
