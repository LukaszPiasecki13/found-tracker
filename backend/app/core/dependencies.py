from collections.abc import Callable
from contextlib import AbstractContextManager

from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.sql.factory import SQLConnectionFactory

# A module's `entrypoints.py` is the only non-HTTP caller of `session_scope()`
# (ADR-0002); it never commits, so the transaction boundary stays with the
# service's `repo.transaction()`, exactly like the request session below.
type SessionScope = Callable[[], AbstractContextManager[Session]]

# =============================================================================
# Factory Instances (Singletons)
# =============================================================================

sql_factory = SQLConnectionFactory()

# =============================================================================
# SQL Database Setup
# =============================================================================


def _create_sql_engine() -> Engine:
    """Create a new SQLAlchemy engine based on current settings."""
    settings = get_settings()
    return sql_factory.get_or_create_engine(
        settings.database_url, settings.database_schema
    )


# Initialize SQL engine and session factory
_sql_engine = _create_sql_engine()
_sql_session_factory = sql_factory.create_session_factory(
    _sql_engine,
    use_scoped_session=False,
)

# FastAPI dependency for SQL sessions
get_sql_session = sql_factory.get_session_dependency(_sql_session_factory)
get_db = get_sql_session

# Non-HTTP session lifecycle (ADR-0002): open, roll back on error, always
# close - never commit. Used only from a module's `entrypoints.py`.
session_scope: SessionScope = sql_factory.create_session_scope(_sql_session_factory)


def provide[T](builder: Callable[[Session], T]) -> Callable[[Session], T]:
    """Expose a `wiring.py` builder as a FastAPI dependency on the request
    session (ADR-0002): `get_x = provide(build_x)`. Assign the result to a
    module-level name - it is the key for `dependency_overrides`."""

    def dependency(session: Session = Depends(get_db)) -> T:
        return builder(session)

    return dependency


def get_sql_engine() -> Engine:
    """Return the process-wide engine (health checks, maintenance tasks)."""
    return _sql_engine


def dispose_sql_engines() -> None:
    """Release pooled connections on application shutdown."""
    sql_factory.dispose_all()
