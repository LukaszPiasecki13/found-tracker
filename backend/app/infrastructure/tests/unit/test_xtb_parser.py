"""`XtbParser` on synthetic reports built in memory - no bank file, no database."""

import re
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import Workbook

from app.core.import_parser import ImportParseError, ImportParser
from app.infrastructure.import_parsers import XtbParser
from app.infrastructure.import_parsers import xtb as xtb_module
from app.infrastructure.tests.xtb_report import (
    COMPLETE_CASH_TOTAL,
    build_xtb_report,
    cash_row,
    closed_row,
    transfer_out_row,
)

D = Decimal


@pytest.fixture
def parser() -> XtbParser:
    return XtbParser()


def test_parser_satisfies_the_port(parser: XtbParser) -> None:
    port: ImportParser = parser
    assert port.parser_id == "xtb"


def test_each_cash_operation_becomes_one_row_of_the_right_type(
    parser: XtbParser,
) -> None:
    result = parser.parse(build_xtb_report())

    assert result.issues == []
    assert [row.operation_type for row in result.rows] == [
        "deposit",
        "buy",
        "buy",
        "interest",
        "fee",
        "sell",
        "dividend",
        "withdrawal",
    ]
    # One row per source row: the "Total" line is not an operation.
    assert [row.row_number for row in result.rows] == [6, 7, 8, 9, 10, 11, 12, 13]


def test_trade_quantity_and_price_come_from_the_comment_and_amount_is_absolute(
    parser: XtbParser,
) -> None:
    rows = parser.parse(build_xtb_report()).rows
    buy, sell = rows[1], rows[5]

    assert (buy.ticker, buy.exchange_hint) == ("DNP.PL", "PL")
    assert (buy.quantity, buy.price, buy.amount) == (D("10"), D("40.000"), D("400"))
    # "CLOSE BUY 4/10 @ 50.000": 4 of the 10 are sold.
    assert (sell.quantity, sell.price, sell.amount) == (D("4"), D("50.000"), D("200"))
    assert rows[0].amount == D("5000")
    assert rows[7].amount == D("300")


def test_asset_class_comes_from_category_column_for_trades(
    parser: XtbParser,
) -> None:
    """Category column values: STOCK -> Stock, ETF -> Etf, other -> title case."""
    # The default report has trades with category values; asset_class should be set.
    rows = parser.parse(build_xtb_report()).rows
    buy = rows[1]
    # build_xtb_report() trades have category values, check asset_class is populated
    # The actual category values come from xtb_report.py; we test that they're read.
    assert buy.asset_class == "Stock"


def test_cash_rows_have_no_asset_and_zero_quantity(parser: XtbParser) -> None:
    deposit = parser.parse(build_xtb_report()).rows[0]

    assert (deposit.ticker, deposit.exchange_hint) == (None, None)
    assert (deposit.quantity, deposit.price) == (D("0"), D("0"))


def test_dates_are_aware_utc(parser: XtbParser) -> None:
    first = parser.parse(build_xtb_report()).rows[0]

    assert first.operation_date == datetime(2026, 1, 10, 10, tzinfo=UTC)


@pytest.mark.parametrize(
    ("serial", "expected"),
    [
        (46057.0, datetime(2026, 2, 4, tzinfo=UTC)),
        (44185.5, datetime(2020, 12, 20, 12, tzinfo=UTC)),
        (46014.45, datetime(2025, 12, 23, 10, 48, tzinfo=UTC)),
    ],
)
def test_excel_serials_convert_with_the_1900_system(
    serial: float, expected: datetime
) -> None:
    assert xtb_module._timestamp(serial) == expected


def test_external_refs_tell_open_from_close_and_carry_source_id_and_time(
    parser: XtbParser,
) -> None:
    rows = parser.parse(build_xtb_report()).rows

    bases = [row.external_ref.split(":")[:4] for row in rows]
    assert bases == [
        ["xtb", "cash", "1", "2026-01-10T10"],
        ["xtb", "pos", "100", "open"],
        ["xtb", "pos", "101", "open"],
        ["xtb", "cash", "4", "2026-01-15T10"],
        ["xtb", "cash", "5", "2026-01-15T11"],
        ["xtb", "pos", "100", "close"],
        ["xtb", "cash", "8", "2026-01-22T10"],
        ["xtb", "cash", "7", "2026-01-25T10"],
    ]
    assert rows[1].external_ref.endswith(":2026-01-11T10:00:00+00:00")


def test_a_rows_ref_does_not_depend_on_the_other_rows_of_the_file(
    parser: XtbParser,
) -> None:
    """A later export of the same account must give the same ref to the same
    row, or the row would be recorded twice."""
    shared = cash_row("Deposit", datetime(2026, 1, 1), 10, id_=2222)
    alone = parser.parse(build_xtb_report([shared])).rows[0]
    with_twin = parser.parse(
        build_xtb_report(
            [shared, cash_row("Deposit", datetime(2026, 1, 2), 5, id_=2222)]
        )
    ).rows

    assert alone.external_ref in {row.external_ref for row in with_twin}


def test_an_amount_with_the_wrong_sign_is_an_issue(parser: XtbParser) -> None:
    rows = [cash_row("Deposit", datetime(2026, 1, 1), -10, id_=1)]

    result = parser.parse(build_xtb_report(rows))

    assert result.rows == []
    assert "sign" in result.issues[0].message


def test_float_noise_in_an_amount_is_rounded_to_cents(parser: XtbParser) -> None:
    rows = [cash_row("Deposit", datetime(2026, 1, 1), 331.65000000000003, id_=1)]

    assert parser.parse(build_xtb_report(rows)).rows[0].amount == D("331.65")


def test_ids_shared_by_several_rows_are_made_unique_deterministically(
    parser: XtbParser,
) -> None:
    same_id = [
        cash_row("Deposit", datetime(2026, 1, day), 10, id_=2222) for day in (1, 2, 3)
    ]

    first = parser.parse(build_xtb_report(same_id)).rows
    second = parser.parse(build_xtb_report(same_id)).rows

    refs = [row.external_ref for row in first]
    assert len(set(refs)) == 3
    assert refs == [row.external_ref for row in second]


def test_unknown_type_is_an_issue_not_an_exception(parser: XtbParser) -> None:
    rows = [
        cash_row("Deposit", datetime(2026, 1, 1), 10, id_=1),
        cash_row("Mystery", datetime(2026, 1, 2), 5, id_=2),
    ]

    result = parser.parse(build_xtb_report(rows))

    assert [row.operation_type for row in result.rows] == ["deposit"]
    assert [(i.row_number, "Mystery" in i.message) for i in result.issues] == [
        (7, True)
    ]


def test_trade_with_an_unreadable_comment_is_an_issue(parser: XtbParser) -> None:
    rows = [
        cash_row(
            "Stock purchase",
            datetime(2026, 1, 1),
            -10,
            id_=1,
            ticker="DNP.PL",
            comment="something else",
            position_id="9",
        )
    ]

    result = parser.parse(build_xtb_report(rows))

    assert result.rows == []
    assert len(result.issues) == 1


def test_expectations_come_from_the_other_sheets(parser: XtbParser) -> None:
    expectations = parser.parse(build_xtb_report()).expectations

    assert expectations.cash_total == COMPLETE_CASH_TOTAL
    assert expectations.open_positions == {"DNP.PL": D("6"), "ETFBM40TR.PL": D("2")}
    assert expectations.closed_profit == D("12.50")


def test_missing_total_and_profit_rows_leave_expectations_empty(
    parser: XtbParser,
) -> None:
    report = build_xtb_report(cash_total=None, closed_profit=None, open_positions={})

    expectations = parser.parse(report).expectations

    assert expectations.cash_total is None
    assert expectations.closed_profit is None
    assert expectations.open_positions == {}


# --- sniff ---


def test_sniff_accepts_an_xtb_report(parser: XtbParser) -> None:
    assert parser.sniff("Report.XLSX", build_xtb_report())


def test_sniff_rejects_other_files(parser: XtbParser) -> None:
    other_xlsx = build_xtb_report(include_cash_sheet=False)

    assert not parser.sniff("report.csv", build_xtb_report())
    assert not parser.sniff("report.xlsx", b"not a zip")
    assert not parser.sniff("report.xlsx", other_xlsx)


# --- Unreadable and hostile input ---


def test_a_non_zip_file_is_a_parse_error(parser: XtbParser) -> None:
    with pytest.raises(ImportParseError) as exc_info:
        parser.parse(b"definitely not xlsx")

    assert exc_info.value.code == "IMPORT_PARSE_FAILED"
    assert exc_info.value.status_code == 422


def test_a_workbook_without_the_cash_sheet_is_a_parse_error(parser: XtbParser) -> None:
    with pytest.raises(ImportParseError, match="Cash Operations"):
        parser.parse(build_xtb_report(include_cash_sheet=False))


def test_a_zip_bomb_is_refused_before_it_is_opened(
    parser: XtbParser, monkeypatch: pytest.MonkeyPatch
) -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", b"0" * 2_000_000)
    monkeypatch.setattr(xtb_module, "MAX_COMPRESSION_RATIO", 50)

    with pytest.raises(ImportParseError, match="limits"):
        parser.parse(buffer.getvalue())


def test_too_many_archive_entries_are_refused(
    parser: XtbParser, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(xtb_module, "MAX_ARCHIVE_ENTRIES", 2)

    with pytest.raises(ImportParseError, match="limits"):
        parser.parse(build_xtb_report())


def test_too_many_rows_are_refused(
    parser: XtbParser, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(xtb_module, "MAX_ROWS", 8)

    with pytest.raises(ImportParseError, match="rows"):
        parser.parse(build_xtb_report())


def _with_wrong_sheet_dimensions(report: bytes) -> bytes:
    """The report as XTB writes it: every sheet claims to be one cell."""
    out = BytesIO()
    with (
        zipfile.ZipFile(BytesIO(report)) as source,
        zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename.startswith("xl/worksheets/"):
                data = re.sub(rb'<dimension ref="[^"]*"', b'<dimension ref="A1"', data)
            target.writestr(item, data)
    return out.getvalue()


def test_a_wrong_sheet_dimension_does_not_hide_the_rows(parser: XtbParser) -> None:
    result = parser.parse(_with_wrong_sheet_dimensions(build_xtb_report()))

    assert len(result.rows) == 8
    assert result.expectations.cash_total == COMPLETE_CASH_TOTAL
    assert result.expectations.open_positions


def test_a_cash_sheet_without_a_header_row_is_a_parse_error(parser: XtbParser) -> None:
    workbook = Workbook()
    workbook.active.title = "Cash Operations"
    workbook.active.append(("Account number", 1))
    buffer = BytesIO()
    workbook.save(buffer)

    with pytest.raises(ImportParseError, match="Header"):
        parser.parse(buffer.getvalue())


def test_dividends_carry_their_asset_and_class(parser: XtbParser) -> None:
    dividend = parser.parse(build_xtb_report()).rows[6]

    assert (dividend.operation_type, dividend.ticker) == ("dividend", "DNP.PL")
    assert (dividend.exchange_hint, dividend.asset_class) == ("PL", "Stock")
    assert (dividend.quantity, dividend.amount) == (D("0"), D("6"))


@pytest.mark.parametrize(
    ("source_type", "amount", "booked_as"),
    [
        ("Free funds interest", 3.5, "interest"),
        ("Free funds interest tax", -0.7, "fee"),
        ("Withholding tax", -1.2, "fee"),
        ("SEC fee", -0.1, "fee"),
        ("Swap", -3.0, "fee"),
        ("Close trade", 12.0, "interest"),
        ("Close trade", -12.0, "fee"),
        ("Correction", 5.34, "interest"),
        ("Correction", -1.0, "fee"),
    ],
)
def test_other_cash_is_booked_as_income_or_cost_by_the_sign(
    parser: XtbParser, source_type: str, amount: float, booked_as: str
) -> None:
    rows = [
        cash_row(
            source_type,
            datetime(2026, 1, 1),
            amount,
            id_=1,
            ticker="BITCOIN",
            comment="Profit of position #1",
        )
    ]

    [row] = parser.parse(build_xtb_report(rows)).rows

    assert (row.operation_type, row.amount) == (booked_as, D(str(abs(amount))))
    assert row.ticker is None  # cash without an asset
    assert row.notes == f"{source_type} | BITCOIN | Profit of position #1"


def test_a_dividend_without_a_ticker_is_an_issue(parser: XtbParser) -> None:
    rows = [cash_row("Dividend", datetime(2026, 1, 1), 5, id_=1)]

    result = parser.parse(build_xtb_report(rows))

    assert result.rows == [] and len(result.issues) == 1


# --- Splits (a position transfer in the position sheets) ---

_BOUGHT = datetime(2026, 1, 2, 10)
_MOVED = datetime(2026, 1, 5, 7, 0, 0)
_OPENED = datetime(2026, 1, 5, 7, 30, 0)


def _split_cash_rows() -> list[tuple[object, ...]]:
    return [
        cash_row("Deposit", datetime(2026, 1, 1, 9), 1000, id_=1, comment="Deposit"),
        cash_row(
            "Stock purchase",
            _BOUGHT,
            -200,
            id_=2,
            ticker="DNP.PL",
            comment="OPEN BUY 2 @ 100.000",
            position_id="200",
        ),
        cash_row(
            "Stock sell",
            datetime(2026, 1, 10, 10),
            180,
            id_=3,
            ticker="DNP.PL",
            comment="CLOSE BUY 15/15 @ 12.000",
            position_id="300",
        ),
    ]


def _split_closed_rows() -> list[tuple[object, ...]]:
    return [
        transfer_out_row("DNP.PL", 2, _BOUGHT, _MOVED, "200"),
        closed_row("DNP.PL", 15, _OPENED, datetime(2026, 1, 10, 10), "300"),
    ]


def test_a_position_transfer_is_a_split_with_the_ratio_of_the_volumes(
    parser: XtbParser,
) -> None:
    report = build_xtb_report(
        _split_cash_rows(),
        closed_rows=[
            *_split_closed_rows(),
            closed_row("DNP.PL", 5, _OPENED, datetime(2026, 1, 11, 10), "301"),
        ],
    )

    result = parser.parse(report)

    assert result.issues == []
    [split] = [row for row in result.rows if row.operation_type == "split"]
    assert split.ratio == D("10")  # (15 + 5) / 2
    assert split.operation_date == datetime(2026, 1, 5, 7, 0, tzinfo=UTC)
    assert (split.ticker, split.exchange_hint, split.amount) == ("DNP.PL", "PL", 0)
    assert split.external_ref.startswith("xtb:split:DNP.PL:")
    assert split.row_number > max(r.row_number for r in result.rows if r is not split)


def test_positions_of_the_transfer_that_are_still_open_count_too(
    parser: XtbParser,
) -> None:
    report = build_xtb_report(
        _split_cash_rows(),
        closed_rows=_split_closed_rows(),
        open_lots=[("301", "DNP.PL", 5, _OPENED)],
    )

    [split] = [r for r in parser.parse(report).rows if r.operation_type == "split"]

    assert split.ratio == D("10")


def test_a_position_opened_by_a_cash_row_is_no_part_of_the_transfer(
    parser: XtbParser,
) -> None:
    rows = [
        *_split_cash_rows(),
        cash_row(
            "Stock purchase",
            datetime(2026, 1, 5, 8, 0),
            -50,
            id_=9,
            ticker="DNP.PL",
            comment="OPEN BUY 1 @ 50.000",
            position_id="400",
        ),
    ]
    closed = [
        *_split_closed_rows(),
        closed_row(
            "DNP.PL", 1, datetime(2026, 1, 5, 8, 0), datetime(2026, 1, 12), "400"
        ),
    ]

    [split] = [
        r
        for r in parser.parse(build_xtb_report(rows, closed_rows=closed)).rows
        if r.operation_type == "split"
    ]

    assert split.ratio == D("7.5")  # only the 15 of the transfer over the 2


def test_a_transfer_that_keeps_the_volume_is_not_a_split(parser: XtbParser) -> None:
    report = build_xtb_report(
        _split_cash_rows(),
        closed_rows=[
            transfer_out_row("DNP.PL", 15, _BOUGHT, _MOVED, "200"),
            closed_row("DNP.PL", 15, _OPENED, datetime(2026, 1, 10, 10), "300"),
        ],
    )

    result = parser.parse(report)

    assert [r.operation_type for r in result.rows if r.operation_type == "split"] == []
    assert result.issues == []


def test_a_transfer_without_the_positions_it_opened_is_an_issue(
    parser: XtbParser,
) -> None:
    report = build_xtb_report(
        _split_cash_rows(),
        closed_rows=[transfer_out_row("DNP.PL", 2, _BOUGHT, _MOVED, "200")],
    )

    result = parser.parse(report)

    assert [r for r in result.rows if r.operation_type == "split"] == []
    [issue] = result.issues
    assert "ratio is unknown" in issue.message
