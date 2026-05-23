"""
Unit tests for SQLConnectionFactory.

Tests use mocks - no real database connection is required.
"""

from contextlib import suppress
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from app.infrastructure.sql.factory import SQLConnectionFactory, _mask_url

SQLITE_URL = "sqlite:///test.db"
POSTGRES_URL = "postgresql+psycopg2://user:pass@localhost:5432/testdb"
POSTGRES_URL_2 = "postgresql+psycopg2://user:pass@localhost:5432/otherdb"


class TestSQLConnectionFactory:
    """Unit tests for SQL connection factory."""

    @patch("app.infrastructure.sql.factory.create_engine")
    def test_init_creates_engine_once(self, mock_create_engine):
        """get_or_create_engine creates exactly one engine for the provided URL."""
        mock_create_engine.return_value = MagicMock()

        factory = SQLConnectionFactory()
        factory.get_or_create_engine(SQLITE_URL)

        mock_create_engine.assert_called_once()
        assert factory._engines[SQLITE_URL] is mock_create_engine.return_value

    @patch("app.infrastructure.sql.factory.create_engine")
    def test_sqlite_url_sets_check_same_thread(self, mock_create_engine):
        """SQLite URLs get check_same_thread=False in connect_args."""
        mock_create_engine.return_value = MagicMock()

        factory = SQLConnectionFactory()
        factory.get_or_create_engine(SQLITE_URL)

        call_kwargs = mock_create_engine.call_args[1]
        assert call_kwargs["connect_args"] == {"check_same_thread": False}

    @patch("app.infrastructure.sql.factory.create_engine")
    def test_non_sqlite_url_has_no_connect_args(self, mock_create_engine):
        """Non-SQLite URLs do not receive check_same_thread."""
        mock_create_engine.return_value = MagicMock()

        factory = SQLConnectionFactory()
        factory.get_or_create_engine(POSTGRES_URL)

        call_kwargs = mock_create_engine.call_args[1]
        assert call_kwargs["connect_args"] == {}

    @patch("app.infrastructure.sql.factory.create_engine")
    def test_pool_pre_ping_is_enabled(self, mock_create_engine):
        """Engine is created with pool_pre_ping=True."""
        mock_create_engine.return_value = MagicMock()

        factory = SQLConnectionFactory()
        factory.get_or_create_engine(POSTGRES_URL)

        assert mock_create_engine.call_args[1]["pool_pre_ping"] is True

    def test_create_session_factory_returns_scoped_session_by_default(self):
        """Default session factory should be scoped and bind sessions to the engine."""
        factory = SQLConnectionFactory()
        engine = create_engine("sqlite+pysqlite:///:memory:")

        session_factory = factory.create_session_factory(engine)

        assert isinstance(session_factory, scoped_session)
        session = session_factory()
        assert isinstance(session, Session)
        session.close()
        session_factory.remove()

    def test_create_session_factory_can_return_plain_sessionmaker(self):
        """The factory can also return a plain sessionmaker when requested."""
        factory = SQLConnectionFactory()
        engine = create_engine("sqlite+pysqlite:///:memory:")

        session_factory = factory.create_session_factory(
            engine,
            autoflush=True,
            use_scoped_session=False,
        )

        assert isinstance(session_factory, sessionmaker)
        assert session_factory.kw["autoflush"] is True
        session = session_factory()
        assert isinstance(session, Session)
        session.close()

    @patch("app.infrastructure.sql.factory.create_engine")
    def test_same_url_returns_cached_engine(self, mock_create_engine):
        """Same URL should hit the cache and avoid a second engine."""
        mock_create_engine.return_value = MagicMock()

        factory = SQLConnectionFactory()
        first_engine = factory.get_or_create_engine(SQLITE_URL)
        engine_again = factory.get_or_create_engine(SQLITE_URL)

        assert first_engine is engine_again
        mock_create_engine.assert_called_once()

    @patch("app.infrastructure.sql.factory.create_engine")
    def test_different_urls_create_separate_engines(self, mock_create_engine):
        """Different URLs produce separate, independently cached engines."""
        engine_a, engine_b = MagicMock(), MagicMock()
        mock_create_engine.side_effect = [engine_a, engine_b]

        factory = SQLConnectionFactory()
        first_engine = factory.get_or_create_engine(POSTGRES_URL)
        second_engine = factory.get_or_create_engine(POSTGRES_URL_2)

        assert first_engine is engine_a
        assert second_engine is engine_b
        assert mock_create_engine.call_count == 2

    @patch("app.infrastructure.sql.factory.create_engine")
    def test_engines_dict_tracks_all_created_engines(self, mock_create_engine):
        """_engines cache contains an entry for every unique URL used."""
        engine_a, engine_b = MagicMock(), MagicMock()
        mock_create_engine.side_effect = [engine_a, engine_b]

        factory = SQLConnectionFactory()
        factory.get_or_create_engine(POSTGRES_URL)
        factory.get_or_create_engine(POSTGRES_URL_2)

        assert POSTGRES_URL in factory._engines
        assert POSTGRES_URL_2 in factory._engines
        assert len(factory._engines) == 2

    @patch("app.infrastructure.sql.factory.create_engine")
    def test_dispose_all_disposes_every_engine(self, mock_create_engine):
        """dispose_all calls dispose() on every cached engine."""
        engine_a, engine_b = MagicMock(), MagicMock()
        mock_create_engine.side_effect = [engine_a, engine_b]

        factory = SQLConnectionFactory()
        factory.get_or_create_engine(POSTGRES_URL)
        factory.get_or_create_engine(POSTGRES_URL_2)

        factory.dispose_all()

        engine_a.dispose.assert_called_once()
        engine_b.dispose.assert_called_once()

    @patch("app.infrastructure.sql.factory.create_engine")
    def test_dispose_all_clears_cache(self, mock_create_engine):
        """dispose_all empties the _engines dict."""
        mock_create_engine.return_value = MagicMock()

        factory = SQLConnectionFactory()
        factory.get_or_create_engine(POSTGRES_URL)
        factory.dispose_all()

        assert factory._engines == {}

    @patch("app.infrastructure.sql.factory.create_engine")
    def test_dispose_all_continues_on_error(self, mock_create_engine):
        """dispose_all does not raise if one engine's dispose() fails."""
        broken_engine = MagicMock()
        broken_engine.dispose.side_effect = RuntimeError("connection lost")
        mock_create_engine.return_value = broken_engine

        factory = SQLConnectionFactory()
        factory.get_or_create_engine(POSTGRES_URL)

        # Must not raise
        factory.dispose_all()

        assert factory._engines == {}


class TestGetSessionDependency:
    """Tests for the session dependency generator."""

    @patch("app.infrastructure.sql.factory.create_engine")
    def test_get_session_dependency_yields_session(self, mock_create_engine):
        """get_session_dependency yields a session object."""
        mock_create_engine.return_value = MagicMock()
        factory = SQLConnectionFactory()

        mock_session = MagicMock()
        session_factory = MagicMock(return_value=mock_session)

        gen = factory.get_session_dependency(session_factory)()
        session = next(gen)

        assert session is mock_session

    @patch("app.infrastructure.sql.factory.create_engine")
    def test_get_session_dependency_closes_on_exit(self, mock_create_engine):
        """get_session_dependency closes the session in the finally block."""
        mock_create_engine.return_value = MagicMock()
        factory = SQLConnectionFactory()

        mock_session = MagicMock()
        session_factory = MagicMock(return_value=mock_session)

        gen = factory.get_session_dependency(session_factory)()
        next(gen)
        with suppress(StopIteration):
            next(gen)

        mock_session.close.assert_called_once()

    @patch("app.infrastructure.sql.factory.create_engine")
    def test_get_session_dependency_closes_on_exception(self, mock_create_engine):
        """get_session_dependency closes the session even if the consumer raises."""
        mock_create_engine.return_value = MagicMock()
        factory = SQLConnectionFactory()

        mock_session = MagicMock()
        session_factory = MagicMock(return_value=mock_session)

        gen = factory.get_session_dependency(session_factory)()
        next(gen)
        with suppress(ValueError):
            gen.throw(ValueError("consumer error"))

        mock_session.close.assert_called_once()

    def test_get_session_dependency_works_with_real_session_factory(self):
        """The dependency should work with a real SQLAlchemy session factory."""
        factory = SQLConnectionFactory()
        engine = MagicMock()
        session_factory = factory.create_session_factory(engine)

        dependency = factory.get_session_dependency(session_factory)
        gen = dependency()
        session = next(gen)

        assert isinstance(session, Session)
        with suppress(StopIteration):
            next(gen)


class TestMaskUrl:
    """Tests for the URL masking helper."""

    def test_masks_password_in_postgres_url(self):
        url = "postgresql+psycopg2://admin:secret123@db.host:5432/mydb"
        result = _mask_url(url)
        assert "secret123" not in result
        assert "admin" in result
        assert "***" in result

    def test_passes_through_sqlite_url(self):
        url = "sqlite:///local.db"
        result = _mask_url(url)
        assert result == url

    def test_passes_through_url_without_credentials(self):
        url = "postgresql://localhost/mydb"
        result = _mask_url(url)
        assert result == url
