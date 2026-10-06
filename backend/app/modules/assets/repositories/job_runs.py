"""Job-run rows: one per daily job, locked while a request starts it (ADR-0017)."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.infrastructure.sql.repository import SQLRepository
from app.modules.assets.models.job_runs import JobRun


class JobRunRepository(SQLRepository):
    """Repository for `JobRun` rows; the service decides the transaction."""

    def lock_for_start(
        self, job_key: str, *, now: datetime, stale_before: datetime
    ) -> bool:
        """Lock the job's row (`SKIP LOCKED`: a concurrent start is skipped, not
        waited for) and start the run when it never started, or when an earlier run
        started before `stale_before` and never finished. `False` when the run is
        already started or finished, or is locked by another transaction."""
        self.session.execute(
            insert(JobRun)
            .values(job_key=job_key, status="idle")
            .on_conflict_do_nothing(index_elements=[JobRun.job_key])
        )
        stmt = (
            select(JobRun)
            .where(JobRun.job_key == job_key)
            .with_for_update(skip_locked=True)
        )
        row = self.session.execute(stmt).scalar_one_or_none()
        if row is None:
            return False
        abandoned = row.last_finished_at is None and (
            row.last_started_at is not None and row.last_started_at < stale_before
        )
        if row.last_started_at is not None and not abandoned:
            return False
        row.last_started_at = now
        row.last_finished_at = None
        row.status = "running"
        self.flush()
        return True

    def finish(self, job_key: str, *, now: datetime) -> None:
        """Mark the run finished; no-op when the row is missing."""
        row = self.session.get(JobRun, job_key)
        if row is None:
            return
        row.last_finished_at = now
        row.status = "idle"
        self.flush()
