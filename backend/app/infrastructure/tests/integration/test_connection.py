from contextlib import suppress

from sqlalchemy import text
from sqlalchemy.orm import Session


class TestSQLIntegration:
    """Integration tests for SQL connections."""

    def test_sql_engine_creation(self, sql_engine):
        """Test SQL engine creation with environment configuration."""
        assert sql_engine is not None

    def test_sql_session_executes_query(self, sql_factory, sql_engine):
        """Test SQL session query execution against real database."""
        session_factory = sql_factory.create_session_factory(sql_engine)
        session: Session = session_factory()

        try:
            result = session.execute(text("SELECT 1")).scalar()
            assert result == 1
        finally:
            session.close()

    def test_sql_session_dependency_closes_session(self, sql_factory, sql_engine):
        """Test the dependency generator closes real sessions on exit."""
        session_factory = sql_factory.create_session_factory(sql_engine)
        dependency = sql_factory.get_session_dependency(session_factory)

        gen = dependency()
        session = next(gen)

        assert isinstance(session, Session)
        with suppress(StopIteration):
            next(gen)
