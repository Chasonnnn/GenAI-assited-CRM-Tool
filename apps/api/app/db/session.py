from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, settings


def _create_engine_with_settings(config: Settings, *, metrics: bool = False):
    url = make_url(config.DATABASE_URL.get_secret_value())
    backend = url.get_backend_name()

    connect_args = {}
    if backend.startswith("postgresql"):
        connect_args["options"] = "-c timezone=utc"
        if metrics:
            connect_args["connect_timeout"] = 2
            connect_args["options"] += " -c statement_timeout=1000 -c lock_timeout=500"

    pool_kwargs = {
        "pool_pre_ping": config.DB_POOL_PRE_PING,
    }
    if backend.startswith("postgresql"):
        pool_kwargs.update(
            {
                "pool_size": 1 if metrics else config.DB_POOL_SIZE,
                "max_overflow": 0 if metrics else config.DB_MAX_OVERFLOW,
                "pool_timeout": 0.1 if metrics else config.DB_POOL_TIMEOUT,
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
    return _create_engine_with_settings(config)


def create_metrics_engine_with_settings(config: Settings):
    """A single, fail-fast connection independent of the request pool."""
    return _create_engine_with_settings(config, metrics=True)


engine = create_engine_with_settings(settings)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metrics_engine = create_metrics_engine_with_settings(settings)
MetricsSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=metrics_engine)
