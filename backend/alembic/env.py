import os
import sys
from contextlib import suppress
from functools import lru_cache

# Make the backend/app package importable when running alembic from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text

# Register all models so Alembic can detect their tables
from alembic import context
from app.core.config import get_settings
from app.infrastructure.sql import models_registry  # noqa: F401
from app.infrastructure.sql.base import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the database URL from .env so alembic.ini does not need it
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Autogenerate compares this metadata against the live schema
target_metadata = Base.metadata

# Use the configured schema for Alembic's version table and include schema-aware
# autogeneration so migrations respect the application's schema setting.
_VERSION_TABLE_SCHEMA = settings.database_schema


@lru_cache(maxsize=1)
def get_managed_tables() -> set[str]:
    """Resolve managed table names from imported SQLAlchemy model metadata."""
    managed_tables: set[str] = set()
    for table in Base.metadata.tables.values():
        if table.schema in (None, _VERSION_TABLE_SCHEMA):
            managed_tables.add(table.name)
    return managed_tables


def include_name(name, type_, parent_names):
    """Filter so autogenerate only considers our application's tables."""
    if type_ == "table":
        schema_name = parent_names.get("schema_name")
        managed_tables = get_managed_tables()
        return schema_name == _VERSION_TABLE_SCHEMA and name in managed_tables
    return True


def configure_context(**kwargs) -> None:
    """Apply the shared Alembic configuration for offline and online runs."""
    context.configure(
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema=_VERSION_TABLE_SCHEMA,
        include_name=include_name,
        **kwargs,
    )


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


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
    configure_context(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})

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
        # Ensure the target schema exists for databases that support schemas (Postgres).
        try:
            dialect_name = connection.dialect.name
        except Exception:
            dialect_name = None

        if dialect_name == "postgresql":
            with suppress(Exception):
                connection.execute(
                    text(f'CREATE SCHEMA IF NOT EXISTS "{_VERSION_TABLE_SCHEMA}"')
                )
                # Best-effort: on failure, continue and let migrations report errors.

        configure_context(connection=connection)

        with context.begin_transaction():
            context.run_migrations()

        if connection.in_transaction():
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
