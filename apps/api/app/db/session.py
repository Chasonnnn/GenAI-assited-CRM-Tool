from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, settings


def create_engine_with_settings(config: Settings):
    url = make_url(config.DATABASE_URL)
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
                "pool_size": config.DB_POOL_SIZE,
                "max_overflow": config.DB_MAX_OVERFLOW,
                "pool_timeout": config.DB_POOL_TIMEOUT,
                "pool_recycle": config.DB_POOL_RECYCLE,
            }
        )

    return create_engine(config.DATABASE_URL, connect_args=connect_args, **pool_kwargs)


engine = create_engine_with_settings(settings)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
