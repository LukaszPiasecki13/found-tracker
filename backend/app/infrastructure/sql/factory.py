import logging
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager

from sqlalchemy import Connection, Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, scoped_session, sessionmaker

logger = logging.getLogger(__name__)


def _mask_url(url: str) -> str:
    """Mask password in a database URL for safe logging."""
    try:
        return make_url(url).render_as_string(hide_password=True)
    except ArgumentError:
        return "<unparseable database url>"


class SQLConnectionFactory:
    """
    Manages SQLAlchemy engine lifecycle and session creation.

    Engines are cached by database URL - each URL gets one engine for the
    lifetime of this factory instance. Sessions are scoped per request.
    """

    def __init__(self) -> None:
        self._engines: dict[str | tuple[str, str], Engine] = {}

    def get_or_create_engine(
        self, database_url: str, target_schema: str | None = None
    ) -> Engine:
        """Return cached engine for the given URL, or create and cache a new one."""
        cache_key: str | tuple[str, str]
        cache_key = (
            database_url if target_schema is None else (database_url, target_schema)
        )
        if cache_key in self._engines:
            logger.debug("Returning cached engine for: %s", _mask_url(database_url))
            return self._engines[cache_key]

        logger.info("Creating new engine for: %s", _mask_url(database_url))
        connect_args = (
            {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        )
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args=connect_args,
        )

        if engine.dialect.name == "postgresql" and target_schema:
            schema_sql = engine.dialect.identifier_preparer.quote(target_schema)

            def _on_begin(connection: Connection) -> None:
                # Supabase uses a transaction-mode connection pooler. A
                # session-level SET executed only when a physical connection
                # is opened can be lost between requests and make one request
                # read another schema. Apply the schema to every transaction.
                connection.exec_driver_sql(f"SET LOCAL search_path TO {schema_sql}")

            event.listen(engine, "begin", _on_begin)

        self._engines[cache_key] = engine
        return engine

    def create_session_factory(
        self,
        engine: Engine,
        autocommit: bool = False,
        autoflush: bool = False,
        use_scoped_session: bool = True,
    ) -> scoped_session[Session] | sessionmaker[Session]:
        """Create session factory bound to the given engine."""
        factory = sessionmaker(
            autocommit=autocommit,
            autoflush=autoflush,
            expire_on_commit=False,
            bind=engine,
        )
        if use_scoped_session:
            return scoped_session(factory)
        return factory

    def create_session_scope(
        self,
        session_factory: sessionmaker[Session] | scoped_session[Session],
    ) -> Callable[[], AbstractContextManager[Session]]:
        """Build `session_scope()` (ADR-0002): open a session, roll back on any
        exception (including `SystemExit`) and always close it - but never commit.
        The commit boundary belongs to the caller's `repo.transaction()`.

        Callable only from a module's `entrypoints.py`; `get_session_dependency`
        below is built on the same mechanism for the HTTP request session.
        """

        @contextmanager
        def scope() -> Generator[Session]:
            session = session_factory()
            try:
                yield session
            except BaseException:
                try:
                    session.rollback()
                except Exception:
                    logger.exception("Rollback failed after an earlier error")
                raise
            else:
                if session.new or session.dirty or session.deleted:
                    logger.warning(
                        "session_scope closed with uncommitted changes "
                        "(%d new, %d dirty, %d deleted) - missing transaction()?",
                        len(session.new),
                        len(session.dirty),
                        len(session.deleted),
                    )
            finally:
                session.close()
                if hasattr(session_factory, "remove"):
                    session_factory.remove()

        return scope

    def get_session_dependency(
        self,
        session_factory: sessionmaker[Session] | scoped_session[Session],
    ) -> Callable[[], Generator[Session]]:
        """Create FastAPI dependency function for database sessions."""
        scope = self.create_session_scope(session_factory)

        def session_generator() -> Generator[Session]:
            with scope() as session:
                yield session

        return session_generator

    def dispose_all(self) -> None:
        """Dispose all cached engines. Call on application shutdown."""
        for url, engine in list(self._engines.items()):
            try:
                engine.dispose()
            except Exception as exc:
                database_url = url if isinstance(url, str) else url[0]
                logger.warning(
                    "Error disposing engine for %s: %s",
                    _mask_url(database_url),
                    exc,
                )
        self._engines.clear()
