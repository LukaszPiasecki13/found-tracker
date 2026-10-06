"""CSV export adapter from DM BOŚ (Polish bank) for ImportParser port.

Operations parsed from CSV: Data; Rachunek; Waluta; Tytuł operacji; Wartość.
Uses only stdlib (csv, re, datetime, decimal).
Encoding: UTF-8 with BOM or Windows-1250 fallback.
"""

import re
from csv import DictReader
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import md5

from app.core.import_parser import (
    ImportExpectations,
    ImportParseError,
    ImportParser,
    ParsedRow,
    ParseIssue,
    ParseResult,
)

# The export names no exchange, so each listed ticker gets the suffix its Yahoo
# symbol needs (verified for every instrument in the example file). Other tickers,
# e.g. US stocks, stay bare.
_EXCHANGE_BY_TICKER: dict[str, str] = {
    "PZU": "PL",
    "XTB": "PL",
    "DNP": "PL",
    "ETFBM40TR": "PL",
    "ETFBS80TR": "PL",
    "SXR8": "DE",
    "LYMS": "DE",
    "DTLA": "L",
    "ANXU": "L",
}


_BASE_CURRENCY = "PLN"
# "Wymiana waluty PLN/USD 3.6118": the account's own conversion, PLN per one unit.
_PLN_EXCHANGE = re.compile(r"^Wymiana waluty PLN/([A-Z]{3}) ([\d,.]+)$")
_GROSZ = Decimal("0.01")


def _listing(ticker: str) -> tuple[str, str | None]:
    """The source ticker with its exchange suffix, and the exchange code."""
    exchange = _EXCHANGE_BY_TICKER.get(ticker)
    if exchange is None:
        return ticker, None
    return f"{ticker}.{exchange}", exchange


class BosParser(ImportParser):
    """Reads CSV exports from DM BOŚ (Polish bank)."""

    parser_id: str = "bos"

    def sniff(self, filename: str, content: bytes) -> bool:
        """Detect if content is a BOŚ CSV file by checking filename and header.

        Returns False if file does not end with .csv, if decoding fails, or if
        the header does not match expected columns.
        Never raises.
        """
        try:
            if not filename.lower().endswith(".csv"):
                return False

            # Try UTF-8 first (with BOM), fallback to Windows-1250
            text: str
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                try:
                    text = content.decode("windows-1250")
                except UnicodeDecodeError:
                    return False

            lines = text.split("\n")
            if not lines:
                return False

            # Parse first line as CSV header manually
            header_fields = lines[0].strip().split(";")
            if not header_fields:
                return False

            expected_columns = {
                "Data",
                "Rachunek",
                "Waluta",
                "Tytuł operacji",
                "Wartość",
            }
            actual_columns = set(header_fields)
            return expected_columns == actual_columns
        except Exception:
            return False

    def parse(self, content: bytes) -> ParseResult:
        """Parse BOŚ CSV into ParseResult with rows, issues, and expectations.

        Raises ImportParseError if the file structure is invalid (bad header).
        Individual row issues are captured in ParseIssue without exception.
        """
        # Decode content
        text: str
        try:
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = content.decode("windows-1250")
        except UnicodeDecodeError as err:
            msg = "File encoding is not UTF-8 or Windows-1250"
            raise ImportParseError(msg) from err

        lines = text.strip().split("\n")
        if not lines:
            raise ImportParseError("File is empty")

        # Parse header manually
        header_fields = lines[0].strip().split(";")
        expected_columns = {
            "Data",
            "Rachunek",
            "Waluta",
            "Tytuł operacji",
            "Wartość",
        }
        if set(header_fields) != expected_columns:
            raise ImportParseError(
                f"CSV header mismatch. Expected columns: {expected_columns}"
            )

        # Convert data lines to dict rows (skip header, handle empty lines)
        raw_rows: list[dict[str, str]] = []
        for line in lines[1:]:
            if not line.strip():
                continue
            # Use DictReader to parse each line individually
            # Use restval="" to avoid None for missing fields
            row_reader = DictReader(
                [line],
                fieldnames=header_fields,
                delimiter=";",
                restval="",
            )
            row = next(row_reader, None)
            if row is not None:
                raw_rows.append(row)

        # Find and mark currency exchange pairs to skip
        skip_indices = self._find_and_skip_currency_exchanges(raw_rows)
        rates = self._pln_rates(raw_rows)

        # Process rows
        parsed_rows: list[ParsedRow] = []
        issues: list[ParseIssue] = []
        open_positions: dict[str, Decimal] = {}

        for idx, raw_row in enumerate(raw_rows):
            if idx in skip_indices:
                continue

            row_number = idx + 2  # +1 for header, +1 for 1-based indexing
            self._process_data_row(
                raw_row, row_number, parsed_rows, issues, open_positions, rates
            )

        # Generate stable external_refs for rows without natural ID
        parsed_rows = self._stable_refs(parsed_rows)

        # Build expectations
        expectations = ImportExpectations(
            open_positions=open_positions,
            cash_total=None,
            closed_profit=None,
        )

        return ParseResult(rows=parsed_rows, issues=issues, expectations=expectations)

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        """Parse DD.MM.YYYY format to UTC datetime.

        Returns None if format is invalid.
        """
        try:
            return datetime.strptime(date_str, "%d.%m.%Y").replace(tzinfo=UTC)
        except ValueError, AttributeError:
            return None

    @staticmethod
    def _parse_amount(amount_str: str) -> Decimal | None:
        """Parse amount string (decimal separator , or .) to Decimal.

        Returns None if parsing fails or value is NaN/Infinity.
        """
        if not amount_str:
            return None
        try:
            # Normalize: replace , with .
            normalized = amount_str.replace(",", ".")
            number = Decimal(normalized)
            # Reject NaN and Infinity
            if not number.is_finite():
                return None
            return number
        except InvalidOperation:
            return None

    @staticmethod
    def _extract_ticker(title: str) -> str | None:
        """Extract ticker from transaction title.

        Example: 'Rozliczenie transakcji kupna: NAME (ISIN) TICKER QUANTITY x PRICE'
        Returns the ticker symbol or None if not found.
        """
        # Pattern: ) followed by spaces, then ticker (letters/digits/dots),
        # then space/digit
        match = re.search(r"\)\s+([A-Z0-9.]+)\s+[\d.]+\s+x", title)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_fx_rate(title: str) -> Decimal | None:
        """Extract exchange rate from currency exchange title.

        Example: 'Wymiana waluty PLN/EUR 4.5675'
        Returns the rate as Decimal or None if not found.
        """
        match = re.search(r"([\d,.]+)$", title.strip())
        if match:
            rate_str = match.group(1).replace(",", ".")
            try:
                return Decimal(rate_str)
            except InvalidOperation:
                return None
        return None

    def _find_and_skip_currency_exchanges(self, rows: list[dict[str, str]]) -> set[int]:
        """Find pairs of currency exchange rows and return indices to skip.

        Currency exchange rows have title matching 'Wymiana waluty X/Y {rate}'.
        Pairs are identified by same date and matching title pattern.
        Unpaired (odd) exchange row becomes a ParseIssue instead of being skipped.

        Returns set of row indices (in raw_rows) to completely skip.
        """
        skip_indices: set[int] = set()
        matched_pairs: set[int] = set()

        exchange_pattern = r"^Wymiana waluty\s+[A-Z]+/[A-Z]+\s+[\d,.]+$"

        for i, row in enumerate(rows):
            if i in matched_pairs:
                continue

            title = row.get("Tytuł operacji", "").strip()
            if not re.match(exchange_pattern, title):
                continue

            # Found first exchange, look for second with same date and title
            date1 = row.get("Data", "").strip()
            for j in range(i + 1, len(rows)):
                if j in matched_pairs:
                    continue
                row2 = rows[j]
                title2 = row2.get("Tytuł operacji", "").strip()
                date2 = row2.get("Data", "").strip()

                # Check if same date and same title
                if date1 == date2 and title == title2:
                    # Found a pair, mark both to skip
                    skip_indices.add(i)
                    skip_indices.add(j)
                    matched_pairs.add(i)
                    matched_pairs.add(j)
                    break

        return skip_indices

    def _parse_operation(
        self,
        title: str,
        amount: Decimal,
        operation_date: datetime,
        currency: str,
        row_number: int,
    ) -> ParsedRow | ParseIssue | None:
        """Parse operation type and fields from title.

        Returns ParsedRow, ParseIssue, or None if pattern doesn't match.

        Regexes use atomic patterns (no nested quantifiers) to prevent ReDoS.
        """
        # Normalize whitespace to prevent ReDoS on long titles
        title = " ".join(title.split())

        # Pattern 1: Deposit "Przelew do DM BOŚ"
        if re.match(r"^Przelew do DM BOŚ$", title):
            return ParsedRow(
                row_number=row_number,
                operation_type="deposit",
                operation_date=operation_date,
                amount=abs(amount),
                external_ref="",  # Will be set by _stable_refs
                ticker=None,
                quantity=Decimal("0"),
                price=Decimal("0"),
                notes="",
            )

        # Pattern 2: Withdrawal "Zwrot nadpłaty - ..."
        match = re.match(r"^Zwrot nadpłaty\s+-\s+(.+)$", title)
        if match:
            return ParsedRow(
                row_number=row_number,
                operation_type="withdrawal",
                operation_date=operation_date,
                amount=abs(amount),
                external_ref="",
                ticker=None,
                quantity=Decimal("0"),
                price=Decimal("0"),
                notes=match.group(1),
            )

        # Try buy transaction
        if result := self._try_buy(title, amount, operation_date, row_number):
            return result

        # Try sell transaction
        if result := self._try_sell(title, amount, operation_date, row_number):
            return result

        # Try dividend (brutto or netto)
        if result := self._try_dividends(title, amount, operation_date, row_number):
            return result

        # Try fee
        if result := self._try_fee(title, amount, operation_date, row_number):
            return result

        # No pattern matched
        return ParseIssue(
            row_number=row_number,
            message=f"Unrecognized operation type: {title}",
            raw={"title": title},
        )

    @staticmethod
    def _pln_rates(
        raw_rows: list[dict[str, str]],
    ) -> dict[str, list[tuple[datetime, Decimal]]]:
        """The conversions the file itself applies: per currency, (day, PLN per one
        unit) in date order, taken from its PLN exchange rows."""
        rates: dict[str, list[tuple[datetime, Decimal]]] = {}
        for row in raw_rows:
            title = " ".join(row.get("Tytuł operacji", "").split())
            match = _PLN_EXCHANGE.match(title)
            currency = row.get("Waluta", "").strip()
            if match is None or match.group(1) != currency:
                continue
            day = BosParser._parse_date(row.get("Data", "").strip())
            rate = BosParser._parse_amount(match.group(2))
            if day is None or rate is None or rate <= 0:
                continue
            rates.setdefault(currency, []).append((day, rate))
        for entries in rates.values():
            entries.sort(key=lambda entry: entry[0])
        return rates

    @staticmethod
    def _rate_on(
        rates: dict[str, list[tuple[datetime, Decimal]]],
        currency: str,
        day: datetime,
    ) -> Decimal | None:
        """PLN per one unit of `currency` on `day`: the file's latest conversion on
        or before that day, else its first one after it; `None` when the file has no
        conversion for the currency."""
        entries = rates.get(currency)
        if not entries:
            return None
        earlier = [rate for when, rate in entries if when <= day]
        return earlier[-1] if earlier else entries[0][1]

    def _process_data_row(
        self,
        raw_row: dict[str, str],
        row_number: int,
        parsed_rows: list[ParsedRow],
        issues: list[ParseIssue],
        open_positions: dict[str, Decimal],
        rates: dict[str, list[tuple[datetime, Decimal]]],
    ) -> None:
        """Process a single CSV row; update parsed_rows, issues, and positions."""
        # Parse date
        date_str = raw_row.get("Data", "").strip()
        operation_date = self._parse_date(date_str)
        if operation_date is None:
            issues.append(
                ParseIssue(
                    row_number=row_number,
                    message=f"Invalid date format: {date_str}",
                    raw=raw_row,
                )
            )
            return

        # Parse amount
        amount_str = raw_row.get("Wartość", "").strip()
        amount = self._parse_amount(amount_str)
        if amount is None:
            issues.append(
                ParseIssue(
                    row_number=row_number,
                    message=f"Invalid amount format: {amount_str}",
                    raw=raw_row,
                )
            )
            return

        currency = raw_row.get("Waluta", "").strip()
        if currency != _BASE_CURRENCY:
            # The amount is in the row's currency (USD, EUR); the portfolio books PLN.
            rate = self._rate_on(rates, currency, operation_date)
            if rate is None:
                issues.append(
                    ParseIssue(
                        row_number=row_number,
                        message=f"No PLN rate for {currency} in the file",
                        raw=raw_row,
                    )
                )
                return
            amount = (amount * rate).quantize(_GROSZ)
        title = raw_row.get("Tytuł operacji", "").strip()

        # Try to match operation type
        result = self._parse_operation(
            title, amount, operation_date, currency, row_number
        )
        if isinstance(result, ParseIssue):
            issues.append(result)
        elif result is not None:
            parsed_row = result
            parsed_rows.append(parsed_row)

            # Track open positions for buy/sell
            if parsed_row.operation_type in ("buy", "sell"):
                ticker = parsed_row.ticker
                if ticker:
                    current = open_positions.get(ticker, Decimal("0"))
                    if parsed_row.operation_type == "buy":
                        open_positions[ticker] = current + parsed_row.quantity
                    else:  # sell
                        open_positions[ticker] = current - parsed_row.quantity

    def _try_buy(
        self,
        title: str,
        amount: Decimal,
        operation_date: datetime,
        row_number: int,
    ) -> ParsedRow | ParseIssue | None:
        """Try to parse buy transaction."""
        # Try full format first: NAME (ISIN) TICKER QTY x PRICE
        match = re.match(
            r"^Rozliczenie transakcji kupna: ([^(]+) \(([A-Z0-9]{12})\) "
            r"([A-Z0-9.]+) ([\d,.]+) x ([\d,.]+) ([A-Z]+).*nr (\S+)$",
            title,
        )
        if match and len(match.groups()) == 7:
            ticker = match.group(3)
            qty_str = match.group(4).replace(",", ".")
            price_str = match.group(5).replace(",", ".")
            ref = match.group(7)
            return self._build_trade_row(
                "buy",
                ticker,
                qty_str,
                price_str,
                ref,
                amount,
                operation_date,
                row_number,
                title,
            )

        # Try short format: NAME (ISIN) QTY x PRICE (ticker = name)
        match = re.match(
            r"^Rozliczenie transakcji kupna: ([A-Z0-9.]+) \(([A-Z0-9]{12})\) "
            r"([\d,.]+) x ([\d,.]+) ([A-Z]+).*nr (\S+)$",
            title,
        )
        if match:
            ticker = match.group(1).strip()
            qty_str = match.group(3).replace(",", ".")
            price_str = match.group(4).replace(",", ".")
            ref = match.group(6)
            return self._build_trade_row(
                "buy",
                ticker,
                qty_str,
                price_str,
                ref,
                amount,
                operation_date,
                row_number,
                title,
            )

        return None

    def _try_sell(
        self,
        title: str,
        amount: Decimal,
        operation_date: datetime,
        row_number: int,
    ) -> ParsedRow | ParseIssue | None:
        """Try to parse sell transaction."""
        # Try full format first: NAME (ISIN) TICKER QTY x PRICE
        match = re.match(
            r"^Rozliczenie transakcji sprzedaży: ([^(]+) \(([A-Z0-9]{12})\) "
            r"([A-Z0-9.]+) ([\d,.]+) x ([\d,.]+) ([A-Z]+).*nr (\S+)$",
            title,
        )
        if match and len(match.groups()) == 7:
            ticker = match.group(3)
            qty_str = match.group(4).replace(",", ".")
            price_str = match.group(5).replace(",", ".")
            ref = match.group(7)
            return self._build_trade_row(
                "sell",
                ticker,
                qty_str,
                price_str,
                ref,
                amount,
                operation_date,
                row_number,
                title,
            )

        # Try short format: NAME (ISIN) QTY x PRICE (ticker = name)
        match = re.match(
            r"^Rozliczenie transakcji sprzedaży: ([A-Z0-9.]+) \(([A-Z0-9]{12})\) "
            r"([\d,.]+) x ([\d,.]+) ([A-Z]+).*nr (\S+)$",
            title,
        )
        if match:
            ticker = match.group(1).strip()
            qty_str = match.group(3).replace(",", ".")
            price_str = match.group(4).replace(",", ".")
            ref = match.group(6)
            return self._build_trade_row(
                "sell",
                ticker,
                qty_str,
                price_str,
                ref,
                amount,
                operation_date,
                row_number,
                title,
            )

        return None

    def _build_trade_row(
        self,
        operation_type: str,
        ticker: str,
        qty_str: str,
        price_str: str,
        ref: str,
        amount: Decimal,
        operation_date: datetime,
        row_number: int,
        title: str,
    ) -> ParsedRow | ParseIssue:
        """Build a trade (buy/sell) row after successful regex match."""
        try:
            qty = Decimal(qty_str)
            price = Decimal(price_str)
        except InvalidOperation:
            msg = f"Invalid quantity or price in {operation_type} transaction: {title}"
            return ParseIssue(
                row_number=row_number,
                message=msg,
                raw={"title": title},
            )

        symbol, exchange = _listing(ticker)
        return ParsedRow(
            row_number=row_number,
            operation_type=operation_type,
            operation_date=operation_date,
            amount=abs(amount),
            external_ref=f"bos:{ref}",
            ticker=symbol,
            exchange_hint=exchange,
            quantity=qty,
            price=price,
            notes="",
        )

    def _try_dividends(
        self,
        title: str,
        amount: Decimal,
        operation_date: datetime,
        row_number: int,
    ) -> ParsedRow | ParseIssue | None:
        """Try to parse dividend transaction (brutto or netto)."""
        # Dividend brutto "Wypłata dywidendy TICKER"
        match = re.match(r"^Wypłata dywidendy\s+([A-Z0-9]+)$", title)
        if match:
            ticker = match.group(1)
            symbol, exchange = _listing(ticker)
            return ParsedRow(
                row_number=row_number,
                operation_type="dividend",
                operation_date=operation_date,
                amount=abs(amount),
                external_ref="",
                ticker=symbol,
                exchange_hint=exchange,
                quantity=Decimal("0"),
                price=Decimal("0"),
                notes=f"Dividend {ticker}",
            )

        # Dividend netto "Wypłata dywidendy netto TICKER TAX% CURRENCY"
        match = re.match(
            r"^Wypłata dywidendy netto\s+([A-Z0-9]+)\s+([\d]+)%\s+([A-Z]+)$",
            title,
        )
        if match:
            ticker = match.group(1)
            tax_percent = match.group(2)
            div_currency = match.group(3)
            symbol, exchange = _listing(ticker)
            return ParsedRow(
                row_number=row_number,
                operation_type="dividend",
                operation_date=operation_date,
                amount=abs(amount),
                external_ref="",
                ticker=symbol,
                exchange_hint=exchange,
                quantity=Decimal("0"),
                price=Decimal("0"),
                notes=(f"Dividend netto {ticker} {tax_percent}% {div_currency}"),
            )

        return None

    def _try_fee(
        self,
        title: str,
        amount: Decimal,
        operation_date: datetime,
        row_number: int,
    ) -> ParsedRow | ParseIssue | None:
        """Try to parse fee transaction."""
        match = re.match(r"^Opłata za transakcję\s+\(([A-Z]+)\)$", title)
        if match:
            exchange = match.group(1)
            return ParsedRow(
                row_number=row_number,
                operation_type="fee",
                operation_date=operation_date,
                amount=abs(amount),
                external_ref="",
                ticker=None,
                quantity=Decimal("0"),
                price=Decimal("0"),
                notes=f"Fee: {exchange}",
            )

        return None

    @staticmethod
    def _stable_refs(rows: list[ParsedRow]) -> list[ParsedRow]:
        """Generate stable external_ref for rows without natural ID.

        Rows with empty external_ref get a hash-based stable ref computed from
        operation date, title (from notes/type combo), and amount.
        Duplicates on the same day get a counter suffix.

        Returns list of ParsedRow with external_ref filled in.
        """
        # Count existing natural refs by prefix
        result: list[ParsedRow] = []

        # Now generate refs for rows without them
        ref_counts: dict[str, int] = {}  # hash -> counter

        for row in rows:
            if row.external_ref:
                result.append(row)
                continue

            # Build stable hash from date + type + amount + notes
            date_str = row.operation_date.date().isoformat()
            key_str = f"{date_str}:{row.operation_type}:{row.amount}:{row.notes}"
            key_hash = md5(key_str.encode()).hexdigest()[:8]

            # Count occurrences of this hash on this day
            count = ref_counts.get(key_hash, 0)
            ref_counts[key_hash] = count + 1

            if count > 0:
                stable_ref = f"bos:syn:{key_hash}:{count}"
            else:
                stable_ref = f"bos:syn:{key_hash}"

            # Update row with new ref
            new_row = row.__class__(
                row_number=row.row_number,
                operation_type=row.operation_type,
                operation_date=row.operation_date,
                amount=row.amount,
                external_ref=stable_ref,
                ticker=row.ticker,
                exchange_hint=row.exchange_hint,
                quantity=row.quantity,
                price=row.price,
                fee=row.fee,
                notes=row.notes,
                asset_class=row.asset_class,
                ratio=row.ratio,
            )
            result.append(new_row)

        return result
