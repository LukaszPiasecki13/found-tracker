"""BosParser on synthetic BOŚ CSV files built in memory - no bank file, no database."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.core.import_parser import ImportParseError, ImportParser
from app.infrastructure.import_parsers import BosParser

D = Decimal


@pytest.fixture
def parser() -> BosParser:
    return BosParser()


def _bos_csv(rows: list[str]) -> bytes:
    """Build a BOŚ CSV content from a list of rows (without header)."""
    header = "Data;Rachunek;Waluta;Tytuł operacji;Wartość"
    content = "\n".join([header, *rows])
    return content.encode("utf-8")


def _pln_pair(day: str, currency: str, rate: str) -> list[str]:
    """The two rows of one PLN -> `currency` conversion, as the export lists them."""
    title = f"Wymiana waluty PLN/{currency} {rate}"
    return [
        f"{day};IKE 111111;PLN;{title};-100",
        f"{day};IKE 111111;{currency};{title};100",
    ]


def test_parser_satisfies_the_port(parser: BosParser) -> None:
    port: ImportParser = parser
    assert port.parser_id == "bos"


# AC-01: sniff() tests
class TestSniff:
    def test_recognizes_bos_csv(self, parser: BosParser) -> None:
        content = _bos_csv(["10.10.2023;IKE 111111;PLN;Przelew do DM BOŚ;100"])
        assert parser.sniff("test.csv", content) is True

    def test_rejects_xlsx_file(self, parser: BosParser) -> None:
        assert parser.sniff("test.xlsx", b"not a csv") is False

    def test_rejects_csv_with_wrong_header(self, parser: BosParser) -> None:
        wrong_header = "Data;Rachunek;Waluta;Operacja;Amount"
        content = (wrong_header + "\n10.10.2023;IKE;PLN;Test;100").encode("utf-8")
        assert parser.sniff("test.csv", content) is False

    def test_never_raises(self, parser: BosParser) -> None:
        """sniff() must never raise exceptions."""
        # Empty file
        assert parser.sniff("test.csv", b"") is False
        # Broken encoding
        assert parser.sniff("test.csv", b"\xff\xfe") is False
        # Non-CSV file
        assert parser.sniff("test.txt", _bos_csv([])) is False


# AC-02: Deposit
class TestDeposit:
    def test_single_deposit(self, parser: BosParser) -> None:
        content = _bos_csv(["10.10.2023;IKE 111111;PLN;Przelew do DM BOŚ;100"])
        result = parser.parse(content)

        assert len(result.rows) == 1
        assert len(result.issues) == 0
        row = result.rows[0]
        assert row.operation_type == "deposit"
        assert row.amount == D("100")
        assert row.operation_date == datetime(2023, 10, 10, tzinfo=UTC)
        assert row.ticker is None
        assert row.quantity == D("0")


# AC-03: Withdrawal
class TestWithdrawal:
    def test_withdrawal(self, parser: BosParser) -> None:
        content = _bos_csv(
            [
                "4.12.2023;IKE 111111;PLN;Zwrot nadpłaty - "
                "przekroczony limit wpłat na IKE/IKZE 827212;50"
            ]
        )
        result = parser.parse(content)

        assert len(result.rows) == 1
        row = result.rows[0]
        assert row.operation_type == "withdrawal"
        assert row.amount == D("50")


# AC-04: Currency exchange pairs are skipped
class TestCurrencyExchanges:
    def test_single_exchange_pair_is_skipped(self, parser: BosParser) -> None:
        content = _bos_csv(
            [
                "10.10.2023;IKE 111111;PLN;Wymiana waluty PLN/EUR 4.5675;-100",
                "10.10.2023;IKE 111111;EUR;Wymiana waluty PLN/EUR 4.5675;100",
            ]
        )
        result = parser.parse(content)

        assert len(result.rows) == 0
        assert len(result.issues) == 0

    def test_multiple_exchange_pairs(self, parser: BosParser) -> None:
        content = _bos_csv(
            [
                "5.01.2024;IKE 111111;PLN;Wymiana waluty PLN/EUR 4.3320;-100",
                "5.01.2024;IKE 111111;EUR;Wymiana waluty PLN/EUR 4.3320;100",
                "6.01.2024;IKE 111111;EUR;Wymiana waluty EUR/USD 1.0941;-100",
                "6.01.2024;IKE 111111;USD;Wymiana waluty EUR/USD 1.0941;100",
                "10.10.2023;IKE 111111;PLN;Przelew do DM BOŚ;1000",
            ]
        )
        result = parser.parse(content)

        # 4 exchange rows skipped, 1 deposit parsed
        assert len(result.rows) == 1
        assert result.rows[0].operation_type == "deposit"

    def test_unpaired_exchange_generates_issue(self, parser: BosParser) -> None:
        # Per DEC-05: currency exchange pairs are skipped. Unpaired exchange
        # does not match any known pattern → ParseIssue
        content = _bos_csv(
            [
                "10.10.2023;IKE 111111;PLN;Wymiana waluty PLN/EUR 4.5675;-100",
                "10.10.2023;IKE 111111;EUR;Wymiana waluty PLN/EUR 4.5675;100",
                "10.10.2023;IKE 111111;EUR;Wymiana waluty EUR/USD 1.0941;-100",
            ]
        )
        result = parser.parse(content)

        # Paired exchange rows skipped (first 2), unpaired generates issue
        assert len(result.rows) == 0
        assert len(result.issues) == 1
        assert "unrecognized" in result.issues[0].message.lower()


# AC-05: Buy transaction
class TestBuy:
    def test_buy_transaction(self, parser: BosParser) -> None:
        content = _bos_csv(
            [
                *_pln_pair("10.10.2023", "EUR", "4.5675"),
                "10.10.2023;IKE 111111;EUR;Rozliczenie transakcji kupna: "
                "ISHARES CORE S&P 500 UCITS (IE00B5BMR087) SXR8 5.000000 x "
                "429.016000 EUR nr Z00117791368;2145.08",
            ]
        )
        result = parser.parse(content)

        assert len(result.rows) == 1
        row = result.rows[0]
        assert row.operation_type == "buy"
        assert row.ticker == "SXR8.DE"
        assert row.exchange_hint == "DE"
        assert row.quantity == D("5.000000")
        assert row.price == D("429.016000")
        assert row.external_ref == "bos:Z00117791368"
        # The EUR amount is booked in PLN at the file's conversion rate.
        assert row.amount == D("9797.65")


# AC-06: Sell transaction
class TestSell:
    def test_sell_transaction(self, parser: BosParser) -> None:
        content = _bos_csv(
            [
                "25.03.2025;IKE 111111;PLN;Rozliczenie transakcji sprzedaży: "
                "DINOPL (PLDINPL00011) DNP 15.000000 x 456.100000 PLN "
                "nr 000000003502;43"
            ]
        )
        result = parser.parse(content)

        assert len(result.rows) == 1
        row = result.rows[0]
        assert row.operation_type == "sell"
        assert row.ticker == "DNP.PL"
        assert row.quantity == D("15.000000")
        assert row.price == D("456.100000")
        assert row.external_ref == "bos:000000003502"


# AC-07: Dividend brutto
class TestDividendBrutto:
    def test_dividend_brutto(self, parser: BosParser) -> None:
        content = _bos_csv(["8.10.2024;IKE 111111;PLN;Wypłata dywidendy PZU;100"])
        result = parser.parse(content)

        assert len(result.rows) == 1
        row = result.rows[0]
        assert row.operation_type == "dividend"
        assert row.ticker == "PZU.PL"
        assert row.amount == D("100")
        assert "PZU" in row.notes


# AC-08: Dividend netto
class TestDividendNetto:
    def test_dividend_netto(self, parser: BosParser) -> None:
        content = _bos_csv(
            [
                *_pln_pair("10.01.2025", "USD", "3.8"),
                "13.03.2025;IKE 111111;USD;Wypłata dywidendy netto MSFT 85% USD;100",
            ]
        )
        result = parser.parse(content)

        assert len(result.rows) == 1
        row = result.rows[0]
        assert row.operation_type == "dividend"
        assert row.ticker == "MSFT"
        assert row.amount == D("380")
        assert "85%" in row.notes
        assert "USD" in row.notes


# AC-09: Fee
class TestFee:
    def test_fee_transaction(self, parser: BosParser) -> None:
        content = _bos_csv(
            [
                *_pln_pair("22.10.2025", "USD", "3.9"),
                "22.10.2025;IKE 111111;USD;Opłata za transakcję (XNAS);-5",
            ]
        )
        result = parser.parse(content)

        assert len(result.rows) == 1
        row = result.rows[0]
        assert row.operation_type == "fee"
        assert row.ticker is None
        assert row.amount == D("19.5")
        assert "XNAS" in row.notes


# AC-10: Unparseable amount and date
class TestParseErrors:
    def test_invalid_amount(self, parser: BosParser) -> None:
        content = _bos_csv(["10.10.2023;IKE 111111;PLN;Przelew do DM BOŚ;ABC"])
        result = parser.parse(content)

        assert len(result.rows) == 0
        assert len(result.issues) == 1
        assert "invalid amount" in result.issues[0].message.lower()

    def test_invalid_date(self, parser: BosParser) -> None:
        content = _bos_csv(["INVALID;IKE 111111;PLN;Przelew do DM BOŚ;100"])
        result = parser.parse(content)

        assert len(result.rows) == 0
        assert len(result.issues) == 1
        assert "invalid date" in result.issues[0].message.lower()

    def test_parser_continues_after_error(self, parser: BosParser) -> None:
        content = _bos_csv(
            [
                "10.10.2023;IKE 111111;PLN;Przelew do DM BOŚ;ABC",
                "11.10.2023;IKE 111111;PLN;Przelew do DM BOŚ;100",
            ]
        )
        result = parser.parse(content)

        assert len(result.rows) == 1
        assert len(result.issues) == 1
        assert result.rows[0].amount == D("100")


# AC-11: Unrecognized operation type
class TestUnrecognized:
    def test_unrecognized_type_is_issue(self, parser: BosParser) -> None:
        content = _bos_csv(["10.10.2023;IKE 111111;PLN;Nieznana operacja;100"])
        result = parser.parse(content)

        assert len(result.rows) == 0
        assert len(result.issues) == 1
        assert "unrecognized" in result.issues[0].message.lower()


# AC-13: Full example.csv
class TestExampleCsv:
    def test_example_csv_parses_without_exception(self, parser: BosParser) -> None:
        # Read example_bos.csv from fixtures directory (not untracked repo root file)
        from pathlib import Path

        fixture_path = Path(__file__).parent / "fixtures" / "example_bos.csv"
        with open(fixture_path, "rb") as f:
            content = f.read()

        result = parser.parse(content)

        # 93 data rows - 20 currency exchange rows = 73 operations
        assert len(result.rows) == 73
        assert len(result.issues) == 0

        # Verify some operations are present
        buy_count = sum(1 for r in result.rows if r.operation_type == "buy")
        sell_count = sum(1 for r in result.rows if r.operation_type == "sell")
        deposit_count = sum(1 for r in result.rows if r.operation_type == "deposit")
        dividend_count = sum(1 for r in result.rows if r.operation_type == "dividend")
        withdrawal_count = sum(
            1 for r in result.rows if r.operation_type == "withdrawal"
        )
        fee_count = sum(1 for r in result.rows if r.operation_type == "fee")

        # Verify counts match expectations
        assert buy_count > 0, "Should have buy operations"
        assert sell_count > 0, "Should have sell operations"
        assert deposit_count > 0, "Should have deposits"
        assert dividend_count > 0, "Should have dividends"
        assert withdrawal_count > 0, "Should have withdrawals"
        assert fee_count > 0, "Should have fees"

        total = (
            buy_count
            + sell_count
            + deposit_count
            + dividend_count
            + withdrawal_count
            + fee_count
        )
        assert total == 73, f"Expected 73 operations, got {total}"


# AC-14: Stable external refs
class TestStableExternalRefs:
    def test_operations_without_natural_id_get_stable_refs(
        self, parser: BosParser
    ) -> None:
        content = _bos_csv(
            [
                "10.10.2023;IKE 111111;PLN;Przelew do DM BOŚ;100",
                "10.10.2023;IKE 111111;PLN;Przelew do DM BOŚ;200",
            ]
        )
        result = parser.parse(content)

        assert len(result.rows) == 2
        # Both should have different stable refs
        refs = [r.external_ref for r in result.rows]
        assert len(set(refs)) == 2
        assert all(ref.startswith("bos:syn:") for ref in refs)

    def test_operations_with_natural_id_keep_it(self, parser: BosParser) -> None:
        content = _bos_csv(
            [
                *_pln_pair("10.10.2023", "EUR", "4.5675"),
                "10.10.2023;IKE 111111;EUR;Rozliczenie transakcji kupna: "
                "ISHARES CORE S&P 500 UCITS (IE00B5BMR087) SXR8 5.000000 x "
                "429.016000 EUR nr Z00117791368;2145.08",
            ]
        )
        result = parser.parse(content)

        row = result.rows[0]
        assert row.external_ref == "bos:Z00117791368"


# AC-15: Open positions tracking
class TestOpenPositions:
    def test_open_positions_from_buys(self, parser: BosParser) -> None:
        content = _bos_csv(
            [
                "10.10.2023;IKE 111111;PLN;Rozliczenie transakcji kupna: "
                "PZU (PLPZU0000011) PZU 28.000000 x 47.010000 PLN "
                "nr 000000000025;10",
                "11.10.2023;IKE 111111;PLN;Rozliczenie transakcji kupna: "
                "PZU (PLPZU0000011) PZU 10.000000 x 47.500000 PLN "
                "nr 000000000026;11",
            ]
        )
        result = parser.parse(content)

        assert "PZU.PL" in result.expectations.open_positions
        assert result.expectations.open_positions["PZU.PL"] == D("38")

    def test_open_positions_with_sells(self, parser: BosParser) -> None:
        content = _bos_csv(
            [
                "10.10.2023;IKE 111111;PLN;Rozliczenie transakcji kupna: "
                "PZU (PLPZU0000011) PZU 28.000000 x 47.010000 PLN "
                "nr 000000000025;10",
                "25.03.2025;IKE 111111;PLN;Rozliczenie transakcji sprzedaży: "
                "PZU (PLPZU0000011) PZU 15.000000 x 57.660000 PLN "
                "nr 000000001688;20",
            ]
        )
        result = parser.parse(content)

        assert "PZU.PL" in result.expectations.open_positions
        assert result.expectations.open_positions["PZU.PL"] == D("13")

    def test_cash_total_and_closed_profit_are_none(self, parser: BosParser) -> None:
        content = _bos_csv(["10.10.2023;IKE 111111;PLN;Przelew do DM BOŚ;100"])
        result = parser.parse(content)

        assert result.expectations.cash_total is None
        assert result.expectations.closed_profit is None


# Edge cases
class TestEdgeCases:
    def test_bom_is_handled(self, parser: BosParser) -> None:
        header = "Data;Rachunek;Waluta;Tytuł operacji;Wartość"
        row = "10.10.2023;IKE 111111;PLN;Przelew do DM BOŚ;100"
        # BOM is part of UTF-8 encoding, will be removed by utf-8-sig
        content = (header + "\n" + row).encode("utf-8-sig")
        result = parser.parse(content)

        assert len(result.rows) == 1
        assert len(result.issues) == 0

    def test_empty_lines_are_ignored(self, parser: BosParser) -> None:
        content = _bos_csv(
            [
                "10.10.2023;IKE 111111;PLN;Przelew do DM BOŚ;100",
                "",
                "11.10.2023;IKE 111111;PLN;Przelew do DM BOŚ;200",
            ]
        )
        result = parser.parse(content)

        assert len(result.rows) == 2

    def test_amount_with_comma_separator(self, parser: BosParser) -> None:
        content = _bos_csv(
            [
                *_pln_pair("10.10.2023", "EUR", "4.5"),
                "10.10.2023;IKE 111111;EUR;Rozliczenie transakcji kupna: "
                "ISHARES (IE00B5BMR087) SXR8 5,5 x 429,016 EUR nr Z00117791368;100,50",
            ]
        )
        result = parser.parse(content)

        assert len(result.rows) == 1
        row = result.rows[0]
        assert row.quantity == D("5.5")
        assert row.price == D("429.016")
        assert row.amount == D("452.25")

    def test_invalid_file_format_raises_error(self, parser: BosParser) -> None:
        content = b"This is not a valid CSV"
        with pytest.raises(ImportParseError):
            parser.parse(content)

    def test_empty_file_raises_error(self, parser: BosParser) -> None:
        with pytest.raises(ImportParseError):
            parser.parse(b"")

    def test_missing_field_in_row_becomes_parse_issue(self, parser: BosParser) -> None:
        """Regression test for M2: missing fields give ParseIssue."""
        # CSV with only 4 fields (missing "Wartość")
        content = (
            "Data;Rachunek;Waluta;Tytuł operacji;Wartość\n"
            "10.10.2023;IKE 111111;PLN;Przelew do DM BOŚ"
        ).encode()
        result = parser.parse(content)

        # Should have 1 issue (invalid amount, not exception)
        assert len(result.rows) == 0
        assert len(result.issues) == 1
        assert "invalid amount" in result.issues[0].message.lower()

    def test_nan_amount_becomes_parse_issue(self, parser: BosParser) -> None:
        """Regression test for M3: NaN should give ParseIssue, not be accepted."""
        content = _bos_csv(["10.10.2023;IKE 111111;PLN;Przelew do DM BOŚ;NaN"])
        result = parser.parse(content)

        assert len(result.rows) == 0
        assert len(result.issues) == 1
        assert "invalid amount" in result.issues[0].message.lower()

    def test_infinity_amount_becomes_parse_issue(self, parser: BosParser) -> None:
        """Regression test for M3: Infinity should give ParseIssue, not be accepted."""
        content = _bos_csv(["10.10.2023;IKE 111111;PLN;Przelew do DM BOŚ;Infinity"])
        result = parser.parse(content)

        assert len(result.rows) == 0
        assert len(result.issues) == 1
        assert "invalid amount" in result.issues[0].message.lower()

    def test_long_title_with_many_spaces_parses_quickly(
        self, parser: BosParser
    ) -> None:
        """Regression test for M1: ReDoS vulnerability with long titles.

        Title with hundreds of spaces should parse in milliseconds (linear time),
        not exponential.
        """
        import time

        # Create a pathological title with many spaces
        long_spaces = "   " * 200  # 600 spaces
        long_title = (
            f"Rozliczenie transakcji kupna:{long_spaces}"
            f"ISHARES CORE S&P 500 UCITS (IE00B5BMR087) SXR8 5.000000 x "
            f"429.016000 EUR nr Z00117791368"
        )
        content = _bos_csv([f"10.10.2023;IKE 111111;EUR;{long_title};5"])

        # Measure parse time
        start = time.perf_counter()
        result = parser.parse(content)
        elapsed = time.perf_counter() - start

        # Should complete in reasonable time (< 100ms)
        assert elapsed < 0.1, f"Parse took {elapsed:.3f}s, expected <0.1s (ReDoS)"
        # Should either parse successfully or give ParseIssue, not hang
        assert len(result.rows) + len(result.issues) > 0


class TestUnlistedTicker:
    def test_unlisted_ticker_keeps_bare_symbol(self, parser: BosParser) -> None:
        content = _bos_csv(
            [
                *_pln_pair("10.11.2025", "USD", "3.6"),
                "10.11.2025;IKE 111111;USD;Rozliczenie transakcji kupna: "
                "Microsoft Corporation (US5949181045) MSFT 3.000000 x 502.545000 "
                "USD nr Z00271811887;1507.64",
            ]
        )
        result = parser.parse(content)

        assert len(result.rows) == 1
        assert result.rows[0].ticker == "MSFT"
        assert result.rows[0].exchange_hint is None


# Foreign-currency amounts are booked in PLN at the rate the file itself applies.
class TestForeignCurrencyAmounts:
    def test_latest_conversion_on_or_before_the_day_is_used(
        self, parser: BosParser
    ) -> None:
        content = _bos_csv(
            [
                *_pln_pair("10.01.2025", "USD", "4"),
                *_pln_pair("20.01.2025", "USD", "3.5"),
                "15.01.2025;IKE 111111;USD;Wypłata dywidendy netto MSFT 85% USD;100",
            ]
        )
        result = parser.parse(content)

        assert result.rows[0].amount == D("400")

    def test_day_before_first_conversion_uses_the_first_one(
        self, parser: BosParser
    ) -> None:
        content = _bos_csv(
            [
                "02.01.2025;IKE 111111;USD;Wypłata dywidendy netto MSFT 85% USD;100",
                *_pln_pair("10.01.2025", "USD", "4"),
            ]
        )
        result = parser.parse(content)

        assert result.rows[0].amount == D("400")

    def test_currency_without_conversion_in_file_is_an_issue(
        self, parser: BosParser
    ) -> None:
        content = _bos_csv(
            ["13.03.2025;IKE 111111;USD;Wypłata dywidendy netto MSFT 85% USD;100"]
        )
        result = parser.parse(content)

        assert result.rows == []
        assert len(result.issues) == 1
        assert "No PLN rate for USD" in result.issues[0].message

    def test_pln_amount_is_not_converted(self, parser: BosParser) -> None:
        content = _bos_csv(
            [
                *_pln_pair("10.01.2025", "USD", "4"),
                "8.10.2024;IKE 111111;PLN;Wypłata dywidendy PZU;100",
            ]
        )
        result = parser.parse(content)

        assert result.rows[0].amount == D("100")
