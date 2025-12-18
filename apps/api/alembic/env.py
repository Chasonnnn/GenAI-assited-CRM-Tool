from logging.config import fileConfig

from sqlalchemy import engine_from_config, inspect, pool, text

from alembic import context

# Import the Base and models for autogenerate support
from app.db.base import Base
# Import all models here so they are registered with Base.metadata
import app.db.models  # noqa: F401

from app.core.config import settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url with the value from settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target_metadata to Base.metadata for autogenerate support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

ALEMBIC_VERSION_TABLE = "alembic_version"
ALEMBIC_VERSION_COL_LEN = 128


def _ensure_alembic_version_table(connection) -> None:
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())

    if ALEMBIC_VERSION_TABLE not in existing_tables:
        connection.execute(
            text(
                f"""
                CREATE TABLE {ALEMBIC_VERSION_TABLE} (
                    version_num VARCHAR({ALEMBIC_VERSION_COL_LEN}) NOT NULL,
                    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                )
                """
            )
        )
        return

    columns = inspector.get_columns(ALEMBIC_VERSION_TABLE)
    for column in columns:
        if column.get("name") != "version_num":
            continue

        col_type = column.get("type")
        current_len = getattr(col_type, "length", None)
        if current_len is not None and current_len < ALEMBIC_VERSION_COL_LEN:
            connection.execute(
                text(
                    f"ALTER TABLE {ALEMBIC_VERSION_TABLE} "
                    f"ALTER COLUMN version_num TYPE VARCHAR({ALEMBIC_VERSION_COL_LEN})"
                )
            )
        break


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        with connection.begin():
            _ensure_alembic_version_table(connection)

        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
