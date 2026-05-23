from sqlalchemy import Engine

from app.core.config import get_settings
from app.infrastructure.sql.factory import SQLConnectionFactory

# =============================================================================
# Factory Instances (Singletons)
# =============================================================================

sql_factory = SQLConnectionFactory()

# =============================================================================
# SQL Database Setup
# =============================================================================


def _create_sql_engine() -> Engine:
    """Create a new SQLAlchemy engine based on current settings."""
    return sql_factory.get_or_create_engine(get_settings().database_url)


# Initialize SQL engine and session factory
_sql_engine = _create_sql_engine()
_sql_session_factory = sql_factory.create_session_factory(_sql_engine)

# FastAPI dependency for SQL sessions
get_sql_session = sql_factory.get_session_dependency(_sql_session_factory)
get_db = get_sql_session
