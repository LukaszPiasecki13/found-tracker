"""The daily refresh claim: the job key of a day, the stale-run cut-off, and the
commit-per-call contract. The row lock itself (`SKIP LOCKED`) is Postgres-only and
is covered by the integration test."""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock

from sqlalchemy.exc import ProgrammingError

from app.modules.assets.services.job_runs import (
    STALE_RUN_AFTER,
    DailyRefreshService,
    daily_job_key,
)

NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)


def _service(jobs: MagicMock) -> DailyRefreshService:
    return DailyRefreshService(jobs, now=lambda: NOW)


def test_the_job_key_names_the_day() -> None:
    assert daily_job_key(date(2026, 10, 6)) == "refresh_2026-10-06"


def test_claim_locks_the_days_row_with_the_stale_cut_off_and_returns_the_answer() -> (
    None
):
    jobs = MagicMock()
    jobs.lock_for_start.return_value = True

    assert _service(jobs).claim(date(2026, 10, 6)) is True

    jobs.lock_for_start.assert_called_once_with(
        "refresh_2026-10-06", now=NOW, stale_before=NOW - STALE_RUN_AFTER
    )


def test_claim_is_committed_by_its_own_transaction() -> None:
    jobs = MagicMock()
    jobs.lock_for_start.return_value = False

    assert _service(jobs).claim(date(2026, 10, 6)) is False

    jobs.transaction.assert_called_once_with()
    jobs.transaction.return_value.__enter__.assert_called_once()
    jobs.transaction.return_value.__exit__.assert_called_once()


def test_finish_marks_the_days_run_finished_at_now() -> None:
    jobs = MagicMock()

    _service(jobs).finish(date(2026, 10, 6))

    jobs.finish.assert_called_once_with("refresh_2026-10-06", now=NOW)
    assert timedelta(minutes=30) == STALE_RUN_AFTER


def test_a_database_error_in_the_claim_is_answered_as_not_claimed() -> None:
    """The first read of the day must not fail when the job table is unavailable."""
    jobs = MagicMock()
    jobs.transaction.side_effect = ProgrammingError("INSERT", {}, Exception("gone"))

    assert _service(jobs).claim(date(2026, 10, 6)) is False
