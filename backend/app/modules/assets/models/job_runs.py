"""Job runs tracking for daily background tasks (Decision DEC-05)."""

from datetime import datetime

from sqlalchemy import DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.sql.base import Base


class JobRun(Base):
    """Tracks execution state of recurring jobs like daily price/FX refresh.

    Used to prevent duplicate runs on the same day (SELECT FOR UPDATE SKIP LOCKED,
    ADR-0001). The `job_key` is unique per job type and day, e.g.
    `refresh_2026-10-06`. After a 30-minute timeout, a stale `status='running'`
    is considered idle and can be reclaimed (Decision DEC-05, R-08)."""

    __tablename__ = "assets_jobrun"

    job_key: Mapped[str] = mapped_column(
        String(64), primary_key=True, index=True, nullable=False
    )
    """Unique job identifier (e.g., `refresh_2026-10-06`)."""

    last_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """When the job most recently began."""

    last_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """When the job most recently completed."""

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="idle", server_default=text("'idle'")
    )
    """Job state: 'idle' or 'running'. After 30 minutes of 'running', treat as idle."""
