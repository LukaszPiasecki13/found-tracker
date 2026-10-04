from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.sql.base import Base

if TYPE_CHECKING:
    from app.modules.portfolios.models.operation import Operation


class ImportBatch(Base):
    """One uploaded file and what became of it (ADR-0018).

    `status` is an `ImportStatus` value (draft, committed, reverted); the same
    file (`sha256`) is one batch per owner. `payload` keeps what the parser
    reported about the file as a whole (`expectations`, `warnings`).
    """

    __tablename__ = "portfolios_import_batch"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    portfolio_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("portfolios_portfolio.id", ondelete="CASCADE"),
        nullable=False,
    )
    parser_id: Mapped[str] = mapped_column(String(40), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    # Up to 10 MB that nothing reads after the upload: loaded on demand.
    file: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    rows: Mapped[list[ImportRow]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="ImportRow.row_number",
    )

    __table_args__ = (
        UniqueConstraint("owner_id", "sha256", name="uq_import_batch_owner_sha256"),
        Index("ix_import_batch_owner_portfolio", "owner_id", "portfolio_id"),
    )


class ImportRow(Base):
    """One parsed row of a batch. `row_status` is an `ImportRowStatus` value;
    `payload` is the parsed row as the parser reported it; `operation_id` is
    set once the row is committed."""

    __tablename__ = "portfolios_import_row"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("portfolios_import_batch.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    row_status: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    dedup_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    asset_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("assets_asset.id"), nullable=True
    )
    operation_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("portfolios_operation.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    batch: Mapped[ImportBatch] = relationship(back_populates="rows")
    operation: Mapped[Operation | None] = relationship()

    __table_args__ = (Index("ix_import_row_batch", "batch_id", "row_number"),)
