import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import TimeoutError
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
    assert engine.hide_parameters is True


def test_metrics_pool_is_isolated_and_connection_timeouts_are_scoped():
    from app.db.session import create_metrics_engine_with_settings

    config = Settings(ENV="test", DATABASE_URL="postgresql+psycopg://user:pass@localhost/db")
    request_engine = create_engine_with_settings(config)
    metrics_engine = create_metrics_engine_with_settings(config)
    try:
        assert request_engine.pool is not metrics_engine.pool
        assert metrics_engine.pool.size() == 1
        assert metrics_engine.pool._max_overflow == 0
        assert metrics_engine.pool.timeout() <= 1
        assert metrics_engine.hide_parameters is True
        captured = []

        def capture_connect(_dialect, _record, _args, kwargs):
            captured.append(kwargs)
            raise RuntimeError("Skip real connection")

        for engine in (request_engine, metrics_engine):
            event.listen(engine, "do_connect", capture_connect)
            with pytest.raises(RuntimeError, match="Skip real connection"):
                engine.connect()
        assert "connect_timeout" not in captured[0]
        assert "statement_timeout" not in captured[0]["options"]
        assert captured[1]["connect_timeout"] <= 5
        assert "statement_timeout=1000" in captured[1]["options"]
        assert "lock_timeout=500" in captured[1]["options"]
    finally:
        request_engine.dispose()
        metrics_engine.dispose()


def test_exhausted_request_pool_does_not_block_metrics_connection(db_engine):
    from app.db.session import create_metrics_engine_with_settings

    config = Settings(
        ENV="test",
        DATABASE_URL=db_engine.url.render_as_string(hide_password=False),
        DB_POOL_SIZE=1,
        DB_MAX_OVERFLOW=0,
        DB_POOL_TIMEOUT=1,
    )
    request_engine = create_engine_with_settings(config)
    metrics_engine = create_metrics_engine_with_settings(config)
    try:
        with request_engine.connect():
            with pytest.raises(TimeoutError):
                request_engine.connect()
            with metrics_engine.connect() as metrics_connection:
                assert metrics_connection.scalar(text("SELECT 1")) == 1
    finally:
        request_engine.dispose()
        metrics_engine.dispose()
