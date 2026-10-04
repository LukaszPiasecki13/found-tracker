"""Import repository: batches with their rows. Every read is scoped to an owner."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.infrastructure.sql.repository import SQLRepository
from app.modules.portfolios.exceptions import ImportBatchNotFoundError
from app.modules.portfolios.models import ImportBatch, ImportRow


class ImportRepository(SQLRepository):
    """Repository for `ImportBatch` (the aggregate root) and its `ImportRow`s."""

    def find_by_sha256(self, owner_id: int, sha256: str) -> ImportBatch | None:
        """The owner's batch of this very file, if it was uploaded before."""
        stmt = (
            select(ImportBatch)
            .where(ImportBatch.owner_id == owner_id, ImportBatch.sha256 == sha256)
            .options(selectinload(ImportBatch.rows))
            .execution_options(populate_existing=True)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def find_owned(self, batch_id: int, owner_id: int) -> ImportBatch | None:
        stmt = (
            select(ImportBatch)
            .where(ImportBatch.id == batch_id, ImportBatch.owner_id == owner_id)
            .options(selectinload(ImportBatch.rows))
            .execution_options(populate_existing=True)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_owned(self, batch_id: int, owner_id: int) -> ImportBatch:
        """Raises ImportBatchNotFoundError (also for another owner's batch)."""
        batch = self.find_owned(batch_id, owner_id)
        if batch is None:
            raise ImportBatchNotFoundError
        return batch

    def list_by_portfolio(self, portfolio_id: int, owner_id: int) -> list[ImportBatch]:
        """The owner's batches of a portfolio, newest first, without the file
        and the rows (a list does not need them)."""
        stmt = (
            select(ImportBatch)
            .where(
                ImportBatch.portfolio_id == portfolio_id,
                ImportBatch.owner_id == owner_id,
            )
            .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
        )
        return list(self.session.execute(stmt).scalars())

    def create(
        self,
        *,
        owner_id: int,
        portfolio_id: int,
        parser_id: str,
        filename: str,
        sha256: str,
        file: bytes,
        status: str,
        payload: dict[str, Any],
        rows: Sequence[ImportRow],
    ) -> ImportBatch:
        batch = ImportBatch(
            owner_id=owner_id,
            portfolio_id=portfolio_id,
            parser_id=parser_id,
            filename=filename,
            sha256=sha256,
            file=file,
            status=status,
            payload=payload,
            rows=list(rows),
        )
        return self.save_new(batch)

    def update(self, batch: ImportBatch) -> ImportBatch:
        return self.persist(batch)

    def delete(self, batch: ImportBatch) -> None:
        self.session.delete(batch)
        self.flush()
