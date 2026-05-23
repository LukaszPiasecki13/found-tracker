import logging
from collections.abc import Callable, Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker

logger = logging.getLogger(__name__)


def _mask_url(url: str) -> str:
    """Mask password in a database URL for safe logging."""
    if "://" in url and "@" in url:
        scheme, rest = url.split("://", 1)
        creds, host = rest.split("@", 1)
        user = creds.split(":")[0] if ":" in creds else creds
        return f"{scheme}://{user}:***@{host}"
    return url


class SQLConnectionFactory:
    """
    Manages SQLAlchemy engine lifecycle and session creation.

    Engines are cached by database URL - each URL gets one engine for the
    lifetime of this factory instance. Sessions are scoped per request.
    """

    def __init__(self) -> None:
        self._engines: dict[str, Engine] = {}

    def get_or_create_engine(self, database_url: str) -> Engine:
        """Return cached engine for the given URL, or create and cache a new one."""
        if database_url in self._engines:
            logger.debug("Returning cached engine for: %s", _mask_url(database_url))
            return self._engines[database_url]

        logger.info("Creating new engine for: %s", _mask_url(database_url))
        connect_args = (
            {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        )
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        self._engines[database_url] = engine
        return engine

    def create_session_factory(
        self,
        engine: Engine,
        autocommit: bool = False,
        autoflush: bool = False,
        use_scoped_session: bool = True,
    ) -> scoped_session[Session] | sessionmaker[Session]:
        """Create session factory bound to the given engine."""
        base_factory = sessionmaker(
            autocommit=autocommit,
            autoflush=autoflush,
            bind=engine,
        )
        return scoped_session(base_factory) if use_scoped_session else base_factory

    def get_session_dependency(
        self,
        session_factory: scoped_session[Session] | sessionmaker[Session],
    ) -> Callable[[], Generator[Session]]:
        """Create FastAPI dependency function for database sessions."""

        def session_generator() -> Generator[Session]:
            session = session_factory()
            try:
                yield session
            finally:
                session.close()

        return session_generator

    def dispose_all(self) -> None:
        """Dispose all cached engines. Call on application shutdown."""
        for url, engine in list(self._engines.items()):
            try:
                engine.dispose()
            except Exception as exc:
                logger.warning("Error disposing engine for %s: %s", _mask_url(url), exc)
        self._engines.clear()


sql_factory = SQLConnectionFactory()
