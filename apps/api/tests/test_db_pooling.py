from sqlalchemy.pool import QueuePool

from app.core.config import Settings
from app.db.session import create_engine_with_settings


def test_create_engine_with_settings_applies_pool_config():
    settings = Settings(
        ENV="test",
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/db",
        DB_POOL_SIZE=7,
        DB_MAX_OVERFLOW=3,
        DB_POOL_TIMEOUT=15,
        DB_POOL_RECYCLE=120,
    )

    engine = create_engine_with_settings(settings)
    pool = engine.pool

    assert isinstance(pool, QueuePool)
    assert pool.size() == 7
    assert pool._max_overflow == 3
    assert pool._timeout == 15
    assert pool._recycle == 120
