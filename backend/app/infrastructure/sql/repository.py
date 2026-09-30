"""Shared SQL repository transaction boundary (ADR-0001)."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy.orm import Session


class SQLRepository:
    """Own SQLAlchemy access so services never depend on Session.

    Repository methods only `add`/`flush`; the commit boundary is the
    service's `with self._repo.transaction():`.
    """

    def __init__(self, session: Session):
        self.session = session

    @contextmanager
    def transaction(self) -> Generator[None]:
        """Commit the enclosed unit of work, rolling back on any exception.

        Replaces the try/except/rollback/raise block that every write path
        would otherwise repeat verbatim.
        """
        try:
            yield
        except Exception:
            self.rollback()
            raise
        self.commit()

    @contextmanager
    def savepoint(self) -> Generator[None]:
        """Nested transaction: an exception rolls back only the enclosed work.

        For a unit inside an already-open `transaction()` that must not poison
        the others.
        """
        with self.session.begin_nested():
            yield

    def flush(self) -> None:
        self.session.flush()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def refresh(self, entity: Any) -> None:
        self.session.refresh(entity)
