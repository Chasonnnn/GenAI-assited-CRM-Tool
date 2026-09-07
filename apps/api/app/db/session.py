from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, settings


def _create_engine(
    config: Settings,
    *,
    pool_size: int,
    max_overflow: int,
    pool_timeout: int,
):
    url = make_url(config.DATABASE_URL.get_secret_value())
    backend = url.get_backend_name()

    connect_args = {}
    if backend.startswith("postgresql"):
        connect_args["options"] = "-c timezone=utc"

    pool_kwargs = {
        "pool_pre_ping": config.DB_POOL_PRE_PING,
    }
    if backend.startswith("postgresql"):
        pool_kwargs.update(
            {
                "pool_size": pool_size,
                "max_overflow": max_overflow,
                "pool_timeout": pool_timeout,
                "pool_recycle": config.DB_POOL_RECYCLE,
            }
        )

    return create_engine(
        config.DATABASE_URL.get_secret_value(),
        connect_args=connect_args,
        hide_parameters=True,
        **pool_kwargs,
    )


def create_engine_with_settings(config: Settings):
    return _create_engine(
        config,
        pool_size=config.DB_POOL_SIZE,
        max_overflow=config.DB_MAX_OVERFLOW,
        pool_timeout=config.DB_POOL_TIMEOUT,
    )


def create_metrics_engine_with_settings(config: Settings):
    """Create a fail-fast pool isolated from request database connections."""
    return _create_engine(
        config,
        pool_size=1,
        max_overflow=0,
        pool_timeout=1,
    )


engine = create_engine_with_settings(settings)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metrics_engine = create_metrics_engine_with_settings(settings)
MetricsSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=metrics_engine,
)
