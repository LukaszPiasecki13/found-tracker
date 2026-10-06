"""The daily refresh starts once per day (ADR-0017): the first request of a day
claims the day's job row; later requests find it claimed."""

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.modules.assets.repositories.job_runs import JobRunRepository

logger = logging.getLogger(__name__)

# A run that started this long ago and never finished counts as abandoned.
STALE_RUN_AFTER = timedelta(minutes=30)


def daily_job_key(day: date) -> str:
    return f"refresh_{day.isoformat()}"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DailyRefreshService:
    """Claims and closes the day's refresh run. Each call commits its own
    transaction (the claim must be visible to the next request at once)."""

    def __init__(
        self,
        job_runs: JobRunRepository,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._jobs = job_runs
        self._now = now

    def claim(self, day: date) -> bool:
        """Whether the caller starts `day`'s refresh. `False` when it is already
        started, finished, or being started by another request. A database error
        here is logged and answered as `False`: the day's refresh is best-effort and
        must not fail the read request that happens to be the first of the day."""
        now = self._now()
        try:
            with self._jobs.transaction():
                return self._jobs.lock_for_start(
                    daily_job_key(day), now=now, stale_before=now - STALE_RUN_AFTER
                )
        except SQLAlchemyError:
            logger.warning("Daily refresh claim failed for %s", day, exc_info=True)
            return False

    def finish(self, day: date) -> None:
        with self._jobs.transaction():
            self._jobs.finish(daily_job_key(day), now=self._now())
