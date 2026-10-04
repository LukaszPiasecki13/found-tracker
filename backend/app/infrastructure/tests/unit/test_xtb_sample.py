"""`XtbParser` on a real bank export, when one is available.

The sample holds personal data, so it is never copied into the repository: point
`PROBA_XLSX_PATH` at it (e.g. the anonymised `proba.xlsx`) to run these tests.
"""

import os
from decimal import Decimal
from pathlib import Path

import pytest

from app.infrastructure.import_parsers import XtbParser

_PATH = os.environ.get("PROBA_XLSX_PATH")

pytestmark = pytest.mark.skipif(
    not _PATH or not Path(_PATH).is_file(), reason="PROBA_XLSX_PATH not set"
)


def test_the_sample_parses_into_ten_operations_without_issues() -> None:
    assert _PATH is not None
    result = XtbParser().parse(Path(_PATH).read_bytes())

    assert result.issues == []
    kinds = sorted(row.operation_type for row in result.rows)
    assert kinds == ["buy", "deposit", "fee", "interest", *["sell"] * 5, "withdrawal"]
    withdrawal = next(r for r in result.rows if r.operation_type == "withdrawal")
    assert withdrawal.operation_date.date().isoformat() == "2026-02-04"
    assert len({row.external_ref for row in result.rows}) == len(result.rows)
    assert result.expectations.open_positions == {"DNP.PL": Decimal("84")}
