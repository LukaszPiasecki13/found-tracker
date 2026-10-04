"""`ImportService` with mocked repository and services and fake parsers: the
upload -> review -> confirm -> revert pipeline, without a file format or a
database. The service must work for any `ImportParser` (AC-15)."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.import_parser import (
    ImportExpectations,
    ImportParseError,
    ParsedRow,
    ParseIssue,
    ParseResult,
)
from app.modules.portfolios.domain import LedgerState, PositionState
from app.modules.portfolios.exceptions import (
    ConcurrentChangeError,
    ImportAlreadyUploadedError,
    ImportBatchHasEditsError,
    ImportBatchNotFoundError,
    ImportBatchStateInvalidError,
    ImportCommitRejectedError,
    ImportFileTooLargeError,
    ImportParserUnknownError,
    ImportUnresolvedRowsError,
    OperationRejectedError,
)
from app.modules.portfolios.models import ImportRow
from app.modules.portfolios.services.import_mapping import (
    app_ticker,
    dedup_key,
    derived_fx_rate,
)
from app.modules.portfolios.services.imports import (
    MAX_IMPORT_FILE_BYTES,
    ImportService,
)

D = Decimal
WHEN = datetime(2026, 1, 10, 10, tzinfo=UTC)
PORTFOLIO_ID = 1
OWNER_ID = 7
DNP = SimpleNamespace(id=50, ticker="DNP.WA", archived_at=None)


def _row(number: int, operation_type: str = "deposit", **values: Any) -> ParsedRow:
    fields: dict[str, Any] = {
        "row_number": number,
        "operation_type": operation_type,
        "operation_date": WHEN,
        "amount": D("100"),
        "external_ref": f"fake:{number}",
    }
    fields.update(values)
    return ParsedRow(**fields)


def _buy(number: int = 7, **values: Any) -> ParsedRow:
    fields: dict[str, Any] = {
        "ticker": "DNP.PL",
        "exchange_hint": "PL",
        "quantity": D("10"),
        "price": D("40"),
        "amount": D("400"),
    }
    fields.update(values)
    return _row(number, "buy", **fields)


class FakeParser:
    """A second bank: nothing of `ImportService` knows its format."""

    def __init__(
        self,
        parser_id: str = "fake",
        accepts: str = ".fake",
        result: ParseResult | None = None,
    ) -> None:
        self.parser_id = parser_id
        self._accepts = accepts
        self.result = result or ParseResult(rows=[])
        self.parsed: list[bytes] = []

    def sniff(self, filename: str, content: bytes) -> bool:
        return filename.endswith(self._accepts)

    def parse(self, content: bytes) -> ParseResult:
        self.parsed.append(content)
        return self.result


@pytest.fixture
def parser() -> FakeParser:
    return FakeParser()


@pytest.fixture
def operations() -> MagicMock:
    mock = MagicMock()
    mock.existing_external_refs.return_value = set()
    mock.preview_state.return_value = LedgerState()
    return mock


@pytest.fixture
def assets() -> MagicMock:
    mock = MagicMock()
    mock.find_by_ticker.side_effect = lambda ticker: DNP if ticker == "DNP.WA" else None
    mock.find_by_id.return_value = DNP
    return mock


@pytest.fixture
def portfolios() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(
    import_repo: MagicMock,
    operations: MagicMock,
    assets: MagicMock,
    portfolios: MagicMock,
    parser: FakeParser,
) -> ImportService:
    import_repo.find_by_sha256.return_value = None

    def create(**values: Any) -> SimpleNamespace:
        batch = _create_batch(**values)
        import_repo.get_owned.return_value = batch
        return batch

    import_repo.create.side_effect = create
    import_repo.update.side_effect = lambda entity: entity
    return ImportService(import_repo, operations, assets, portfolios, [parser])


def _batch(**values: Any) -> SimpleNamespace:
    fields: dict[str, Any] = {
        "id": 9,
        "owner_id": OWNER_ID,
        "portfolio_id": PORTFOLIO_ID,
        "parser_id": "fake",
        "filename": "report.fake",
        "sha256": "0" * 64,
        "status": "draft",
        "payload": {},
        "rows": [],
        "created_at": WHEN,
    }
    fields.update(values)
    return SimpleNamespace(**fields)


def _create_batch(**values: Any) -> SimpleNamespace:
    """`ImportRepository.create`: the stored batch, its rows numbered."""
    for index, row in enumerate(values["rows"], 1):
        row.id = index
    return _batch(**{**values, "id": 9})


def _stored_row(
    number: int, status: str = "ok", asset_id: int | None = None, **payload: Any
) -> ImportRow:
    parsed = _row(number, **payload)
    from app.modules.portfolios.services.import_mapping import row_payload

    row = ImportRow(
        row_number=number,
        row_status=status,
        payload=row_payload(parsed),
        asset_id=asset_id,
    )
    row.id = number
    return row


def _upload(service: ImportService, name: str = "report.fake") -> Any:
    return service.confirm(PORTFOLIO_ID, OWNER_ID, name, b"content")


def _preview(service: ImportService, name: str = "report.fake") -> Any:
    return service.preview(PORTFOLIO_ID, OWNER_ID, name, b"content")


def _statuses(response: Any) -> dict[int, str]:
    return {row.row_number: row.row_status for row in response.rows}


# --- upload ---


# --- confirm ---


# --- revert ---


def test_revert_removes_the_operations_and_unlinks_the_rows(
    service: ImportService,
    operations: MagicMock,
    import_repo: MagicMock,
    session: MagicMock,
) -> None:
    rows = [_stored_row(1, "ok")]
    rows[0].operation_id = 101
    batch = _batch(status="committed", rows=rows)
    import_repo.get_owned.return_value = batch

    service.revert(9, PORTFOLIO_ID, OWNER_ID)

    operations.revert_import_batch_core.assert_called_once_with(
        9, PORTFOLIO_ID, OWNER_ID
    )
    # The batch (its file and rows) goes with the operations.
    import_repo.delete.assert_called_once_with(batch)
    session.commit.assert_called_once()


def test_revert_of_edited_operations_is_refused_and_nothing_changes(
    service: ImportService,
    operations: MagicMock,
    import_repo: MagicMock,
    session: MagicMock,
) -> None:
    batch = _batch(status="committed", rows=[_stored_row(1, "ok")])
    import_repo.get_owned.return_value = batch
    operations.revert_import_batch_core.side_effect = ImportBatchHasEditsError([101])

    with pytest.raises(ImportBatchHasEditsError) as exc_info:
        service.revert(9, PORTFOLIO_ID, OWNER_ID)

    assert exc_info.value.operation_ids == [101]
    assert batch.status == "committed"
    session.rollback.assert_called_once()


def test_revert_needs_a_committed_batch(
    service: ImportService, import_repo: MagicMock
) -> None:
    import_repo.get_owned.return_value = _batch(status="draft")

    with pytest.raises(ImportBatchStateInvalidError):
        service.revert(9, PORTFOLIO_ID, OWNER_ID)


# --- reconciliation report ---


def _expecting(**expectations: Any) -> SimpleNamespace:
    payload = {
        "expectations": {
            "open_positions": {},
            "cash_total": None,
            "closed_profit": None,
            **expectations,
        }
    }
    return _batch(rows=[_stored_row(1, "ok")], payload=payload)


def _report(service: ImportService, import_repo: MagicMock, batch: Any) -> Any:
    import_repo.get_owned.return_value = batch
    return service.get_detail(9, PORTFOLIO_ID, OWNER_ID).reconciliation


def test_report_matches_when_cash_and_positions_agree_with_the_file(
    service: ImportService, operations: MagicMock, import_repo: MagicMock
) -> None:
    operations.preview_state.return_value = LedgerState(
        cash_balance=D("4300.40"),
        positions=(PositionState(DNP.id, D("6"), D("40"), D("1")),),
    )
    batch = _expecting(cash_total="4300.40", open_positions={"DNP.PL": "6"})

    report = _report(service, import_repo, batch)

    assert report.matched is True
    assert report.differences == []
    # A draft is previewed with its `ok` rows applied; nothing is stored.
    assert len(operations.preview_state.call_args.args[2]) == 1


def test_report_lists_every_difference(
    service: ImportService, operations: MagicMock, import_repo: MagicMock
) -> None:
    operations.preview_state.return_value = LedgerState(
        cash_balance=D("4000"),
        positions=(PositionState(DNP.id, D("5"), D("40"), D("1")),),
    )
    batch = _expecting(
        cash_total="4300.40", open_positions={"DNP.PL": "6", "NOPE.PL": "1"}
    )

    report = _report(service, import_repo, batch)

    assert report.matched is False
    assert {d.field: (d.expected, d.actual) for d in report.differences} == {
        "cash_balance": (D("4300.40"), D("4000")),
        "position:DNP.PL": (D("6"), D("5")),
        "position:NOPE.PL": (D("1"), None),
    }


def test_report_flags_a_position_the_file_does_not_have(
    service: ImportService, operations: MagicMock, import_repo: MagicMock
) -> None:
    operations.preview_state.return_value = LedgerState(
        positions=(PositionState(DNP.id, D("3"), D("40"), D("1")),)
    )

    report = _report(service, import_repo, _expecting())

    assert [(d.field, d.expected, d.actual) for d in report.differences] == [
        ("position:DNP.WA", D("0"), D("3"))
    ]


def test_report_of_a_committed_batch_reads_the_portfolio_as_it_is(
    service: ImportService, operations: MagicMock, import_repo: MagicMock
) -> None:
    batch = _expecting()
    batch.status = "committed"

    _report(service, import_repo, batch)

    assert operations.preview_state.call_args.args[2] == []


def test_report_carries_the_ledgers_refusal_instead_of_failing(
    service: ImportService, operations: MagicMock, import_repo: MagicMock
) -> None:
    operations.preview_state.side_effect = OperationRejectedError(
        "Insufficient cash", "INSUFFICIENT_CASH"
    )

    report = _report(service, import_repo, _expecting(cash_total="1"))

    assert (report.matched, report.ledger_error) == (False, "Insufficient cash")


# --- mapping helpers ---


@pytest.mark.parametrize(
    ("raw", "hint", "expected"),
    [
        ("DNP.PL", "PL", "DNP.WA"),
        ("dnp.pl", "PL", "dnp.WA"),
        ("AAPL.US", "US", "AAPL"),
        ("SAP.DE", "DE", "SAP.DE"),
        ("DNP", None, "DNP"),
    ],
)
def test_source_tickers_map_to_the_apps_exchange_suffix(
    raw: str, hint: str | None, expected: str
) -> None:
    assert app_ticker(raw, hint) == expected


def test_the_dedup_key_depends_on_what_makes_an_operation_the_same() -> None:
    base = _buy(1)

    assert dedup_key(base) == dedup_key(_buy(2, external_ref="other"))
    assert dedup_key(base) != dedup_key(_buy(1, quantity=D("11")))
    assert dedup_key(base) != dedup_key(
        _buy(1, operation_date=datetime(2026, 1, 11, tzinfo=UTC))
    )
    # 84 and 84.000 are the same quantity.
    assert dedup_key(_buy(1, quantity=D("84"))) == dedup_key(
        _buy(1, quantity=D("84.000"))
    )


# --- skipped rows, dividends, foreign prices ---


def test_a_domestic_trade_keeps_rate_one_despite_a_cent_of_rounding() -> None:
    assert derived_fx_rate(_buy(1, amount=D("400.01"))) == D("1")
    assert derived_fx_rate(_row(1, "deposit")) == D("1")


def test_cash_may_differ_by_a_cent_per_trade_in_the_report(
    service: ImportService, operations: MagicMock, import_repo: MagicMock
) -> None:
    operations.preview_state.return_value = LedgerState(cash_balance=D("100.03"))
    batch = _expecting(cash_total="100.00")
    batch.rows = [
        _stored_row(n, "ok", operation_type=kind)
        for n, kind in ((1, "buy"), (2, "buy"), (3, "sell"))
    ]

    report = _report(service, import_repo, batch)

    assert report.matched is True  # 3 cents off, 3 trades
    operations.preview_state.return_value = LedgerState(cash_balance=D("100.04"))
    assert _report(service, import_repo, batch).matched is False


# --- preview: nothing is stored ---


def test_preview_classifies_every_row_and_stores_nothing(
    service: ImportService,
    parser: FakeParser,
    operations: MagicMock,
    assets: MagicMock,
    import_repo: MagicMock,
    session: MagicMock,
) -> None:
    parser.result = ParseResult(
        rows=[
            _row(1, "deposit"),
            _buy(2),
            _buy(3, ticker="NOPE.PL"),
            _row(4, "withdrawal", external_ref="fake:known"),
            _row(5, "interest", amount=D("0")),
            _row(6, "mystery"),
        ],
        issues=[ParseIssue(7, "Unreadable comment", {"Type": "Stock sell"})],
    )
    operations.existing_external_refs.return_value = {"fake:known"}

    response = _preview(service)

    assert [(r.row_number, r.row_status) for r in response.rows] == [
        (1, "ok"),
        (2, "ok"),
        (3, "ok"),  # an unknown ticker: the asset is created on import
        (4, "duplicate"),
        (5, "skip"),
        (6, "unrecognized"),
        (7, "unrecognized"),
    ]
    assert response.rows[1].asset_id == DNP.id
    assert "will be created" in response.rows[2].message
    assert all(r.id is None and r.operation_id is None for r in response.rows)
    assert response.existing_batch_id is None
    # The source's `.PL` ticker is looked up as the app's `.WA` one.
    assets.find_by_ticker.assert_any_call("DNP.WA")
    # Nothing was stored: no batch, no operation, no asset, no transaction.
    import_repo.create.assert_not_called()
    import_repo.delete.assert_not_called()
    operations.record_many_core.assert_not_called()
    assets.get_or_create_by_ticker.assert_not_called()
    session.commit.assert_not_called()
    session.add.assert_not_called()


def test_preview_carries_the_report_of_the_file(
    service: ImportService, parser: FakeParser, operations: MagicMock
) -> None:
    parser.result = ParseResult(
        rows=[_row(1)],
        expectations=ImportExpectations(
            open_positions={"DNP.PL": D("6")}, cash_total=D("100.00")
        ),
    )
    operations.preview_state.return_value = LedgerState(cash_balance=D("100"))

    report = _preview(service).reconciliation

    assert [(d.field, d.expected, d.actual) for d in report.differences] == [
        ("position:DNP.PL", D("6"), D("0"))
    ]
    # A preview is replayed with the rows that would be recorded.
    assert [d.row_number for d in operations.preview_state.call_args.args[2]] == [1]


def test_preview_says_when_the_file_was_imported_before(
    service: ImportService, parser: FakeParser, import_repo: MagicMock
) -> None:
    parser.result = ParseResult(rows=[_row(1)])
    import_repo.find_by_sha256.return_value = _batch(id=5, status="committed")

    assert _preview(service).existing_batch_id == 5

    import_repo.find_by_sha256.return_value = _batch(id=6, status="reverted")
    assert _preview(service).existing_batch_id is None


def test_a_dividend_without_an_open_position_is_booked_as_income(
    service: ImportService, parser: FakeParser, operations: MagicMock
) -> None:
    dividend = _row(
        3,
        "dividend",
        ticker="DNP.PL",
        exchange_hint="PL",
        amount=D("6"),
        notes="DNP.PL PLN 1.0/ SHR",
    )
    parser.result = ParseResult(rows=[_buy(2), dividend])
    operations.dividends_without_position.return_value = {3}

    response = _preview(service)

    assert [r.row_status for r in response.rows] == ["ok", "ok"]
    row = response.rows[1]
    assert row.asset_id is None
    assert (row.payload["operation_type"], row.payload["ticker"]) == ("interest", None)
    assert row.payload["notes"] == "Dividend DNP.PL: DNP.PL PLN 1.0/ SHR"
    assert "booked as income" in row.message
    drafts = operations.dividends_without_position.call_args.args[2]
    assert [d.row_number for d in drafts] == [2, 3]


def test_without_dividends_the_ledger_is_not_replayed(
    service: ImportService, parser: FakeParser, operations: MagicMock
) -> None:
    parser.result = ParseResult(rows=[_row(1), _buy(2)])

    _preview(service)

    operations.dividends_without_position.assert_not_called()


def test_a_price_in_another_currency_gets_the_rate_from_the_amount(
    service: ImportService, parser: FakeParser, assets: MagicMock
) -> None:
    # 2 x 120 USD booked as 870 PLN -> rate 3.625.
    parser.result = ParseResult(
        rows=[
            _buy(
                1,
                ticker="NVDA.US",
                exchange_hint="US",
                quantity=D("2"),
                price=D("120"),
                amount=D("870"),
            )
        ]
    )

    row = _preview(service).rows[0]

    assert row.row_status == "ok"
    assert row.payload["fx_rate"] == "3.625000000"
    assert "3.6250" in row.message
    assets.find_by_ticker.assert_any_call("NVDA")  # `.US` has no Yahoo suffix


def test_an_archived_asset_blocks_its_row(
    service: ImportService, parser: FakeParser, assets: MagicMock
) -> None:
    assets.find_by_ticker.side_effect = lambda t: SimpleNamespace(
        id=1, ticker=t, archived_at=WHEN
    )
    parser.result = ParseResult(rows=[_buy(1)])

    row = _preview(service).rows[0]

    assert (row.row_status, "archived" in row.message) == ("unrecognized", True)


def test_a_buy_without_a_ticker_is_unrecognized(
    service: ImportService, parser: FakeParser
) -> None:
    parser.result = ParseResult(rows=[_buy(1, ticker=None)])

    assert _preview(service).rows[0].row_status == "unrecognized"


def test_preview_refuses_a_file_over_the_limit(service: ImportService) -> None:
    with pytest.raises(ImportFileTooLargeError) as exc_info:
        service.preview(
            PORTFOLIO_ID, OWNER_ID, "r.fake", b"0" * (MAX_IMPORT_FILE_BYTES + 1)
        )

    assert (exc_info.value.status_code, exc_info.value.code) == (
        413,
        "IMPORT_FILE_TOO_LARGE",
    )


def test_a_file_no_parser_reads_is_422(service: ImportService) -> None:
    with pytest.raises(ImportParserUnknownError) as exc_info:
        _preview(service, "report.csv")

    assert exc_info.value.code == "IMPORT_PARSER_UNKNOWN"


def test_a_parse_error_stores_nothing(
    service: ImportService, parser: FakeParser, import_repo: MagicMock
) -> None:
    def broken(content: bytes) -> ParseResult:
        raise ImportParseError("bad file")

    parser.parse = broken  # type: ignore[method-assign]

    with pytest.raises(ImportParseError):
        _upload(service)

    import_repo.create.assert_not_called()


def test_a_new_source_needs_no_change_in_the_service(
    import_repo: MagicMock,
    operations: MagicMock,
    assets: MagicMock,
    portfolios: MagicMock,
) -> None:
    """AC-15: the registry alone decides which parser reads a file."""
    import_repo.find_by_sha256.return_value = None
    bank_a = FakeParser("bank_a", ".a", ParseResult(rows=[_row(1)]))
    bank_b = FakeParser("bank_b", ".b", ParseResult(rows=[_row(1)]))
    service = ImportService(
        import_repo, operations, assets, portfolios, [bank_a, bank_b]
    )

    response = service.preview(PORTFOLIO_ID, OWNER_ID, "x.b", b"content")

    assert (bank_a.parsed, bank_b.parsed) == ([], [b"content"])
    assert response.parser_id == "bank_b"


def test_the_portfolio_is_the_owners(
    service: ImportService, portfolios: MagicMock, import_repo: MagicMock
) -> None:
    portfolios.get_owned.side_effect = ImportBatchNotFoundError  # any 404

    with pytest.raises(ImportBatchNotFoundError):
        _preview(service)
    with pytest.raises(ImportBatchNotFoundError):
        _upload(service)

    portfolios.get_owned.assert_called_with(PORTFOLIO_ID, OWNER_ID)
    import_repo.create.assert_not_called()


# --- confirm: the first time anything is stored ---


def test_confirm_stores_the_batch_and_records_the_ok_rows_in_one_transaction(
    service: ImportService,
    parser: FakeParser,
    operations: MagicMock,
    import_repo: MagicMock,
    session: MagicMock,
) -> None:
    parser.result = ParseResult(
        rows=[
            _row(1),
            _buy(2),
            _row(3, external_ref="fake:known"),
            _row(4, amount=D("0")),
        ]
    )
    operations.existing_external_refs.return_value = {"fake:known"}
    operations.record_many_core.return_value = [
        SimpleNamespace(id=101),
        SimpleNamespace(id=102),
    ]

    response = _upload(service)

    kwargs = import_repo.create.call_args.kwargs
    assert (kwargs["status"], kwargs["parser_id"], kwargs["file"]) == (
        "committed",
        "fake",
        b"content",
    )
    drafts = operations.record_many_core.call_args.args[0]
    assert [d.row_number for d in drafts] == [1, 2]
    assert operations.record_many_core.call_args.args[1:] == (PORTFOLIO_ID, OWNER_ID, 9)
    assert [(r.row_number, r.operation_id) for r in response.rows] == [
        (1, 101),
        (2, 102),
        (3, None),
        (4, None),
    ]
    assert response.status == "committed"
    session.commit.assert_called_once()


def test_confirm_refuses_unresolved_rows_and_stores_nothing(
    service: ImportService,
    parser: FakeParser,
    operations: MagicMock,
    import_repo: MagicMock,
) -> None:
    parser.result = ParseResult(
        rows=[_row(1), _row(2, "mystery")],
        issues=[ParseIssue(3, "Unreadable", {})],
    )

    with pytest.raises(ImportUnresolvedRowsError) as exc_info:
        _upload(service)

    assert exc_info.value.row_numbers == [2, 3]
    assert exc_info.value.status_code == 409
    import_repo.create.assert_not_called()
    operations.record_many_core.assert_not_called()


def test_the_same_file_again_returns_its_batch_without_parsing(
    service: ImportService, parser: FakeParser, import_repo: MagicMock
) -> None:
    import_repo.find_by_sha256.return_value = _batch(
        status="committed", rows=[_stored_row(1)]
    )

    response = _upload(service)

    assert response.id == 9
    assert parser.parsed == [b"content"]  # parsed to validate, never stored again
    import_repo.create.assert_not_called()


def test_the_same_file_in_another_portfolio_is_a_conflict(
    service: ImportService, import_repo: MagicMock
) -> None:
    import_repo.find_by_sha256.return_value = _batch(portfolio_id=2, status="committed")

    with pytest.raises(ImportAlreadyUploadedError):
        _upload(service)


def test_a_reverted_import_of_the_file_is_replaced(
    service: ImportService,
    parser: FakeParser,
    operations: MagicMock,
    import_repo: MagicMock,
) -> None:
    reverted = _batch(status="reverted")
    import_repo.find_by_sha256.return_value = reverted
    parser.result = ParseResult(rows=[_row(1)])
    operations.record_many_core.return_value = [SimpleNamespace(id=101)]

    response = _upload(service)

    import_repo.delete.assert_called_once_with(reverted)
    assert response.status == "committed"


def test_confirm_creates_missing_assets_with_the_files_class(
    service: ImportService,
    parser: FakeParser,
    operations: MagicMock,
    assets: MagicMock,
    portfolios: MagicMock,
) -> None:
    portfolios.get_owned.return_value = SimpleNamespace(id=1, base_currency_id=3)
    created = SimpleNamespace(id=77, archived_at=None)
    assets.get_or_create_by_ticker.return_value = created
    parser.result = ParseResult(
        rows=[
            _buy(1, ticker="NEW.PL", asset_class="ETF"),
            _buy(2, ticker="NEW.PL", asset_class="ETF"),
        ]
    )
    operations.record_many_core.return_value = [
        SimpleNamespace(id=101),
        SimpleNamespace(id=102),
    ]

    _upload(service)

    # Once per ticker, in the class of the file, quoted in the portfolio's
    # currency when the provider has no quote.
    assets.get_or_create_by_ticker.assert_called_once_with(
        "NEW.WA", asset_class_name="ETF", fallback_currency_id=3
    )
    drafts = operations.record_many_core.call_args.args[0]
    assert [d.asset_id for d in drafts] == [77, 77]


def test_confirm_refuses_an_asset_that_turns_out_archived(
    service: ImportService,
    parser: FakeParser,
    operations: MagicMock,
    assets: MagicMock,
    portfolios: MagicMock,
    session: MagicMock,
) -> None:
    portfolios.get_owned.return_value = SimpleNamespace(id=1, base_currency_id=3)
    assets.get_or_create_by_ticker.return_value = SimpleNamespace(
        id=77, archived_at=WHEN
    )
    parser.result = ParseResult(rows=[_buy(1, ticker="NEW.PL")])

    with pytest.raises(ImportUnresolvedRowsError):
        _upload(service)

    operations.record_many_core.assert_not_called()
    session.rollback.assert_called_once()


def test_a_ledger_rejection_rolls_everything_back(
    service: ImportService,
    parser: FakeParser,
    operations: MagicMock,
    session: MagicMock,
) -> None:
    parser.result = ParseResult(rows=[_row(1)])
    operations.record_many_core.side_effect = ImportCommitRejectedError(
        1, "Insufficient cash", "INSUFFICIENT_CASH"
    )

    with pytest.raises(ImportCommitRejectedError) as exc_info:
        _upload(service)

    assert exc_info.value.row_number == 1
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_a_unique_race_on_the_source_id_is_a_409(
    service: ImportService, parser: FakeParser, operations: MagicMock
) -> None:
    parser.result = ParseResult(rows=[_row(1)])
    operations.record_many_core.side_effect = IntegrityError("x", {}, Exception())

    with pytest.raises(ConcurrentChangeError):
        _upload(service)


def test_a_split_row_is_recorded_though_it_moves_no_cash(
    service: ImportService,
    parser: FakeParser,
    operations: MagicMock,
) -> None:
    split = _row(
        3,
        "split",
        ticker="DNP.PL",
        exchange_hint="PL",
        amount=D("0"),
        ratio=D("10.000000"),
        notes="Split 10:1 (XTB transfer)",
    )
    parser.result = ParseResult(rows=[_buy(2), split])
    operations.record_many_core.return_value = [
        SimpleNamespace(id=101),
        SimpleNamespace(id=102),
    ]

    response = _upload(service)

    assert _statuses(response) == {2: "ok", 3: "ok"}
    row = next(r for r in response.rows if r.row_number == 3)
    assert row.message and "Split 10:1" in row.message
    drafts = operations.record_many_core.call_args.args[0]
    assert [(d.operation_type, d.ratio) for d in drafts] == [
        ("buy", None),
        ("split", D("10.000000")),
    ]
