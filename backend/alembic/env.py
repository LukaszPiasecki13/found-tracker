import os
import re
import sys
from contextlib import suppress
from functools import lru_cache
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text

from alembic import context

# Make backend/app importable when running alembic from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import get_settings
from app.infrastructure.sql import models_registry  # noqa: F401
from app.infrastructure.sql.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def get_schema_name() -> str | None:
    """
    Resolve target schema in this order:
    1. alembic -x db_schema=dev1 ...
    2. settings.database_schema
    3. public (default for postgres)
    """
    x_args = context.get_x_argument(as_dictionary=True)

    if x_args.get("db_schema"):
        return x_args["db_schema"]

    return settings.database_schema or "public"


_SCHEMA_NAME = get_schema_name()
if _SCHEMA_NAME and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", _SCHEMA_NAME):
    raise RuntimeError("Invalid database schema name")


@lru_cache(maxsize=1)
def get_managed_tables() -> set:
    """Resolve managed table names from imported SQLAlchemy metadata."""
    return {table.name for table in Base.metadata.tables.values()}


def include_name(name, type_, parent_names):
    """
    Filter autogenerate so Alembic only considers our application's tables.
    Works in the currently selected schema via search_path.
    """
    if type_ == "table":
        managed_tables = get_managed_tables()
        return name in managed_tables
    return True


def configure_context(**kwargs) -> None:
    """Apply shared Alembic configuration."""
    context.configure(
        target_metadata=target_metadata,
        include_schemas=False,
        version_table_schema=_SCHEMA_NAME,
        include_name=include_name,
        compare_type=True,
        compare_server_default=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    url = config.get_main_option("sqlalchemy.url")
    configure_context(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        dialect_name = connection.dialect.name

        if dialect_name == "postgresql" and _SCHEMA_NAME:
            schema_sql = connection.dialect.identifier_preparer.quote(_SCHEMA_NAME)
            with suppress(Exception):
                connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_sql}"))

            # Isolate reflection and DDL to the selected schema. Adding public
            # here makes an empty test schema appear populated through
            # PostgreSQL search_path fallback and corrupts autogenerate output.
            connection.execute(text(f"SET search_path TO {schema_sql}"))

            # Ważne dla refleksji/autogenerate
            connection.dialect.default_schema_name = _SCHEMA_NAME

        configure_context(connection=connection)

        with context.begin_transaction():
            context.run_migrations()

        if connection.in_transaction():
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
