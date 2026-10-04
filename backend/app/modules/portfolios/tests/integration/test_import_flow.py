"""Importing an XTB report end to end: real HTTP, real database, a synthetic
report built in memory (no bank file). Needs a database migrated to head."""

from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.tests.xtb_report import (
    COMPLETE_CASH_TOTAL,
    COMPLETE_ROWS,
    COMPLETE_TOTAL_DEPOSITED,
    build_xtb_report,
    cash_row,
)
from app.modules.assets import wiring as assets_wiring
from app.modules.assets.models import Asset, AssetClass, Currency
from app.modules.assets.tests.fakes import FakeMarketDataProvider
from app.modules.portfolios.models import ImportBatch, Operation

D = Decimal
COMPLETE_STATUSES = ["ok"] * 8
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def xtb_assets(
    integration_session: Session, seeded_currency: Currency
) -> dict[str, Asset]:
    """The app's assets for the report's `.PL` tickers (`.WA` in the app);
    existing ones are reused."""
    asset_class = integration_session.scalar(select(AssetClass).order_by(AssetClass.id))
    if asset_class is None:
        pytest.fail("Integration database needs at least one asset class")
    assets: dict[str, Asset] = {}
    for ticker in ("DNP.WA", "ETFBM40TR.WA"):
        asset = integration_session.scalar(select(Asset).where(Asset.ticker == ticker))
        if asset is None:
            asset = Asset(
                ticker=ticker,
                name=ticker,
                asset_class_id=asset_class.id,
                currency_id=seeded_currency.id,
            )
            integration_session.add(asset)
            integration_session.flush()
        assets[ticker] = asset
    return assets


class Api:
    def __init__(self, client: TestClient, headers: dict[str, str]) -> None:
        self.client = client
        self.headers = headers

    def portfolio(self, name: str, currency_id: int) -> int:
        response = self.client.post(
            "/portfolios/",
            headers=self.headers,
            json={"name": name, "base_currency_id": currency_id},
        )
        assert response.status_code == 201, response.text
        return int(response.json()["id"])

    def preview(self, portfolio_id: int, content: bytes) -> Any:
        """What importing the file would do; stores nothing."""
        return self.client.post(
            f"/portfolios/{portfolio_id}/imports/preview",
            headers=self.headers,
            files={"file": ("report.xlsx", content, _XLSX)},
        )

    def import_file(self, portfolio_id: int, content: bytes) -> Any:
        return self.client.post(
            f"/portfolios/{portfolio_id}/imports",
            headers=self.headers,
            files={"file": ("report.xlsx", content, _XLSX)},
        )

    def action(self, portfolio_id: int, batch_id: int, name: str) -> Any:
        return self.client.post(
            f"/portfolios/{portfolio_id}/imports/{batch_id}/{name}",
            headers=self.headers,
        )

    def detail(self, portfolio_id: int) -> dict[str, Any]:
        response = self.client.get(f"/portfolios/{portfolio_id}", headers=self.headers)
        assert response.status_code == 200, response.text
        return dict(response.json())


@pytest.fixture
def api(integration_client: TestClient, auth_headers: dict[str, str]) -> Api:
    return Api(integration_client, auth_headers)


@pytest.fixture
def portfolio_id(api: Api, integration_data: Any, seeded_currency: Currency) -> int:
    return api.portfolio(integration_data.value("imp"), seeded_currency.id)


def _statuses(body: dict[str, Any]) -> list[str]:
    return [row["row_status"] for row in body["rows"]]


def test_preview_stores_nothing_import_does_and_revert_undoes_it(
    api: Api,
    portfolio_id: int,
    xtb_assets: dict[str, Asset],
    integration_session: Session,
) -> None:
    report = build_xtb_report()  # one file: its bytes decide whether it is "the same"
    previewed = api.preview(portfolio_id, report)

    assert previewed.status_code == 200, previewed.text
    preview = previewed.json()
    assert _statuses(preview) == COMPLETE_STATUSES
    assert preview["existing_batch_id"] is None
    assert all(row["id"] is None for row in preview["rows"])
    # Previewed against the file's own totals.
    assert preview["reconciliation"]["matched"] is True, preview["reconciliation"]
    # Nothing of the file is stored: no batch, no row, no operation, no cash.
    integration_session.expire_all()
    assert (
        integration_session.scalars(
            select(ImportBatch).where(ImportBatch.portfolio_id == portfolio_id)
        ).all()
        == []
    )
    assert api.detail(portfolio_id)["cash_balance"] == 0
    assert (
        api.client.get(
            f"/portfolios/{portfolio_id}/imports", headers=api.headers
        ).json()
        == []
    )

    imported = api.import_file(portfolio_id, report)

    assert imported.status_code == 201, imported.text
    body = imported.json()
    assert body["status"] == "committed"
    assert all(row["operation_id"] for row in body["rows"] if row["row_status"] == "ok")
    assert body["reconciliation"]["matched"] is True
    again = api.import_file(portfolio_id, report)
    assert again.json()["id"] == body["id"]
    assert api.preview(portfolio_id, report).json()["existing_batch_id"] == (body["id"])

    detail = api.detail(portfolio_id)
    assert D(str(detail["cash_balance"])) == COMPLETE_CASH_TOTAL
    assert D(str(detail["total_deposited"])) == COMPLETE_TOTAL_DEPOSITED
    held = {p["asset_id"]: p["quantity"] for p in detail["positions"]}
    assert held == {
        xtb_assets["DNP.WA"].id: 6,
        xtb_assets["ETFBM40TR.WA"].id: 2,
    }

    reverted = api.action(portfolio_id, body["id"], "revert")
    assert reverted.status_code == 200, reverted.text
    assert reverted.json()["status"] == "reverted"
    # Nothing of the import stays: no batch, no row, no file.
    gone = api.client.get(
        f"/portfolios/{portfolio_id}/imports/{body['id']}", headers=api.headers
    )
    assert gone.status_code == 404
    assert (
        api.client.get(
            f"/portfolios/{portfolio_id}/imports", headers=api.headers
        ).json()
        == []
    )
    integration_session.expire_all()
    assert (
        integration_session.scalars(
            select(ImportBatch).where(ImportBatch.portfolio_id == portfolio_id)
        ).all()
        == []
    )
    detail = api.detail(portfolio_id)
    assert (detail["cash_balance"], detail["total_deposited"]) == (0, 0)
    assert detail["positions"] == []
    remaining = integration_session.scalars(
        select(Operation).where(Operation.portfolio_id == portfolio_id)
    ).all()
    assert remaining == []


def test_a_second_file_with_the_same_source_ids_records_only_the_new_rows(
    api: Api, portfolio_id: int, xtb_assets: dict[str, Asset]
) -> None:
    assert api.import_file(portfolio_id, build_xtb_report()).status_code == 201
    extra = cash_row("Deposit", datetime(2026, 1, 28), 50, id_=8, comment="Deposit")

    second_file = build_xtb_report([*COMPLETE_ROWS, extra], cash_total=4356.40)

    second = api.preview(portfolio_id, second_file)

    assert second.status_code == 200, second.text
    assert _statuses(second.json()) == [*["duplicate"] * 8, "ok"]
    confirmed = api.import_file(portfolio_id, second_file)
    assert confirmed.status_code == 201, confirmed.text
    assert D(str(api.detail(portfolio_id)["cash_balance"])) == D("4356.40")


def test_commit_creates_an_asset_the_app_does_not_know_yet(
    api: Api,
    portfolio_id: int,
    xtb_assets: dict[str, Asset],
    integration_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No provider quote: the asset falls back to the portfolio's currency.
    monkeypatch.setattr(
        assets_wiring, "build_market_data_provider", lambda: FakeMarketDataProvider()
    )
    rows = [
        *COMPLETE_ROWS[:1],
        cash_row(
            "Stock purchase",
            datetime(2026, 1, 11),
            -10,
            id_=20,
            ticker="ZZZUNKNOWN.PL",
            comment="OPEN BUY 1 @ 10.000",
            position_id="900",
        ),
    ]

    report = build_xtb_report(rows, cash_total=None)

    previewed = api.preview(portfolio_id, report)

    assert _statuses(previewed.json()) == ["ok", "ok"]
    # A preview creates no asset.
    assert (
        integration_session.scalar(select(Asset).where(Asset.ticker == "ZZZUNKNOWN.WA"))
        is None
    )
    confirmed = api.import_file(portfolio_id, report)
    assert confirmed.status_code == 201, confirmed.text
    created = integration_session.scalar(
        select(Asset).where(Asset.ticker == "ZZZUNKNOWN.WA")
    )
    assert created is not None
    assert created.asset_class.name == "Stock"
    assert confirmed.json()["rows"][1]["asset_id"] == created.id


def test_a_history_the_ledger_refuses_stores_nothing(
    api: Api,
    portfolio_id: int,
    xtb_assets: dict[str, Asset],
    integration_session: Session,
) -> None:
    sell_without_buy = cash_row(
        "Stock sell",
        datetime(2026, 1, 11),
        100,
        id_=30,
        ticker="DNP.PL",
        comment="CLOSE BUY 2/2 @ 50.000",
        position_id="901",
    )
    report = build_xtb_report([COMPLETE_ROWS[0], sell_without_buy], cash_total=None)
    previewed = api.preview(portfolio_id, report)
    assert previewed.status_code == 200, previewed.text
    assert "Row 7" in previewed.json()["reconciliation"]["ledger_error"]

    refused = api.import_file(portfolio_id, report)

    assert refused.status_code == 400
    assert refused.json()["code"] == "IMPORT_COMMIT_REJECTED"
    assert "Row 7" in refused.json()["detail"]
    integration_session.expire_all()
    stored = integration_session.scalars(
        select(Operation).where(Operation.portfolio_id == portfolio_id)
    ).all()
    assert stored == []
    assert api.detail(portfolio_id)["cash_balance"] == 0


def test_revert_is_refused_once_an_operation_was_edited_by_hand(
    api: Api, portfolio_id: int, xtb_assets: dict[str, Asset]
) -> None:
    committed = api.import_file(portfolio_id, build_xtb_report()).json()
    batch = committed
    edited_id = committed["rows"][5]["operation_id"]  # the sell row
    patched = api.client.patch(
        f"/portfolios/operations/{edited_id}",
        headers=api.headers,
        json={"notes": "checked by hand"},
    )
    assert patched.status_code == 200, patched.text

    refused = api.action(portfolio_id, batch["id"], "revert")

    assert refused.status_code == 409
    assert refused.json()["code"] == "IMPORT_BATCH_HAS_EDITS"
    assert str(edited_id) in refused.json()["detail"]
    assert D(str(api.detail(portfolio_id)["cash_balance"])) == COMPLETE_CASH_TOTAL


def test_a_file_no_parser_reads_is_422(api: Api, portfolio_id: int) -> None:
    response = api.client.post(
        f"/portfolios/{portfolio_id}/imports",
        headers=api.headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "IMPORT_PARSER_UNKNOWN"


def test_another_users_portfolio_is_not_found(
    api: Api, integration_client: TestClient
) -> None:
    response = api.preview(10**9, build_xtb_report())

    assert response.status_code == 404
    assert response.json()["code"] == "PORTFOLIO_NOT_FOUND"


def test_foreign_trade_dividend_and_other_cash_of_a_real_looking_account(
    api: Api,
    portfolio_id: int,
    xtb_assets: dict[str, Asset],
    integration_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        assets_wiring, "build_market_data_provider", lambda: FakeMarketDataProvider()
    )
    rows = [
        cash_row("Deposit", datetime(2026, 1, 1), 10000, id_=1),
        # 2 x 120 USD booked as 870 PLN.
        cash_row(
            "Stock purchase",
            datetime(2026, 1, 2),
            -870,
            id_=2,
            ticker="ZZFOREIGN.US",
            comment="OPEN BUY 2 @ 120.00",
            position_id="800",
        ),
        cash_row(
            "Dividend",
            datetime(2026, 1, 3),
            1.5,
            id_=3,
            ticker="ZZFOREIGN.US",
            comment="ZZFOREIGN.US USD 0.25/ SHR",
            position_id="800",
        ),
        cash_row(
            "Withholding tax",
            datetime(2026, 1, 3, 1),
            -0.2,
            id_=4,
            ticker="ZZFOREIGN.US",
            comment="WHT 15%",
            position_id="800",
        ),
        cash_row(
            "Stock sell",
            datetime(2026, 1, 4),
            870,
            id_=5,
            ticker="ZZFOREIGN.US",
            comment="CLOSE BUY 2 @ 120.00",
            position_id="800",
        ),
        # Paid after the position was closed: skipped, not a failed import.
        cash_row(
            "Dividend",
            datetime(2026, 1, 5),
            1.5,
            id_=6,
            ticker="ZZFOREIGN.US",
            comment="late payout",
            position_id="800",
        ),
        cash_row("Swap", datetime(2026, 1, 6), -3, id_=7, ticker="BITCOIN"),
    ]

    report = build_xtb_report(
        rows, cash_total=10000 - 870 + 1.5 - 0.2 + 870 + 1.5 - 3, open_positions={}
    )

    previewed = api.preview(portfolio_id, report)

    assert previewed.status_code == 200, previewed.text
    body = previewed.json()
    assert _statuses(body) == ["ok"] * 7
    by_row = {r["row_number"]: r for r in body["rows"]}
    assert "Withholding tax" in by_row[9]["payload"]["notes"]
    assert by_row[9]["payload"]["operation_type"] == "fee"
    assert "booked as income" in by_row[11]["message"]  # no position left
    assert body["reconciliation"]["matched"] is True, body["reconciliation"]

    confirmed = api.import_file(portfolio_id, report)

    assert confirmed.status_code == 201, confirmed.text
    created = integration_session.scalar(
        select(Asset).where(Asset.ticker == "ZZFOREIGN")
    )
    assert created is not None
    operations = integration_session.scalars(
        select(Operation).where(Operation.portfolio_id == portfolio_id)
    ).all()
    assert len(operations) == 7
    assert D(str(api.detail(portfolio_id)["cash_balance"])) == D("9999.80")
