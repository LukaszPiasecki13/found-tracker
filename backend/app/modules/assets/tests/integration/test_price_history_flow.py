"""Price history, exchange-rate history, archiving and backfill against the real
database (each test runs in a rolled-back transaction).

The market-data provider is replaced in `wiring.py`, so no test reaches the
network; background tasks that would open their own session are stubbed.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.conftest import CurrencyCodes, IntegrationData
from app.modules.assets import entrypoints
from app.modules.assets import wiring as assets_wiring
from app.modules.assets.models import Asset, AssetPrice, Currency, FxRate
from app.modules.assets.tests.fakes import FakeMarketDataProvider, make_quote

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeMarketDataProvider:
    provider = FakeMarketDataProvider()
    monkeypatch.setattr(assets_wiring, "build_market_data_provider", lambda: provider)
    return provider


@pytest.fixture
def asset(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency: Currency,
) -> dict[str, object]:
    asset_class = integration_client.post(
        "/assets/asset-classes",
        headers=auth_headers,
        json={"name": integration_data.value("c")[:20]},
    )
    created = integration_client.post(
        "/assets/",
        headers=auth_headers,
        json={
            "ticker": integration_data.value("t")[:20].upper(),
            "name": "Priced asset",
            "asset_class_id": asset_class.json()["id"],
            "currency_id": seeded_currency.id,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def _prices(
    client: TestClient, headers: dict[str, str], asset_id: object, **params: object
) -> dict[str, object]:
    response = client.get(f"/assets/{asset_id}/prices", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_manual_prices_feed_the_series_the_detail_and_the_cache(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    asset: dict[str, object],
) -> None:
    asset_id = asset["id"]
    old_day = TODAY - timedelta(days=30)

    older = integration_client.put(
        f"/assets/{asset_id}/prices/{old_day}",
        headers=auth_headers,
        json={"close": 10.5},
    )
    newer = integration_client.put(
        f"/assets/{asset_id}/prices/{YESTERDAY}",
        headers=auth_headers,
        json={"close": 12},
    )

    assert (older.status_code, newer.status_code) == (200, 200)
    assert newer.json()["source"] == "manual"

    series = _prices(integration_client, auth_headers, asset_id)
    assert [(i["price_date"], i["close"]) for i in series["items"]] == [
        (str(old_day), 10.5),
        (str(YESTERDAY), 12.0),
    ]

    detail = integration_client.get(f"/assets/{asset_id}", headers=auth_headers).json()
    assert detail["current_price"] == 12.0  # the cache follows the newest close
    assert detail["price_date"] == str(YESTERDAY)
    assert (detail["price_source"], detail["stale"]) == ("manual", False)

    # Replacing a day is an upsert, not a duplicate.
    integration_client.put(
        f"/assets/{asset_id}/prices/{YESTERDAY}",
        headers=auth_headers,
        json={"close": 13},
    )
    again = _prices(integration_client, auth_headers, asset_id, **{"from": YESTERDAY})
    assert [i["close"] for i in again["items"]] == [13.0]


def test_forward_fill_covers_every_day_and_is_never_stored(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    asset: dict[str, object],
    integration_session: Session,
) -> None:
    asset_id = asset["id"]
    start = TODAY - timedelta(days=3)
    integration_client.put(
        f"/assets/{asset_id}/prices/{start}", headers=auth_headers, json={"close": 5}
    )

    filled = _prices(
        integration_client,
        auth_headers,
        asset_id,
        **{"from": start, "to": TODAY, "fill": "forward"},
    )

    assert len(filled["items"]) == 4
    assert {i["close"] for i in filled["items"]} == {5.0}
    assert {i["price_date"] for i in filled["items"]} == {str(start)}
    rows = integration_session.execute(
        select(AssetPrice).where(AssetPrice.asset_id == asset_id)
    ).scalars()
    assert len(list(rows)) == 1


def test_a_stale_price_is_flagged_in_the_detail_and_the_data_status(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    asset: dict[str, object],
) -> None:
    asset_id = asset["id"]
    integration_client.put(
        f"/assets/{asset_id}/prices/{TODAY - timedelta(days=30)}",
        headers=auth_headers,
        json={"close": 5},
    )

    detail = integration_client.get(f"/assets/{asset_id}", headers=auth_headers).json()
    status = integration_client.get(
        "/assets/data-status", headers=auth_headers, params={"only_problems": True}
    )

    assert detail["stale"] is True
    assert status.status_code == 200
    mine = [a for a in status.json()["assets"] if a["asset_id"] == asset_id]
    assert [(a["stale"], a["source"]) for a in mine] == [(True, "manual")]


def test_deleting_the_manual_price_falls_back_to_the_provider_close(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    asset: dict[str, object],
    integration_session: Session,
    fake_provider: FakeMarketDataProvider,
) -> None:
    asset_id = asset["id"]
    orm_asset = integration_session.get(Asset, asset_id)
    assert orm_asset is not None
    fake_provider.quotes[orm_asset.ticker] = make_quote(
        orm_asset.ticker, current_price=Decimal("20")
    )
    market_data = assets_wiring.build_market_data_service(integration_session)
    assert market_data.refresh_asset_prices([orm_asset]) == 1
    integration_client.put(
        f"/assets/{asset_id}/prices/{TODAY}", headers=auth_headers, json={"close": 99}
    )

    assert (
        integration_client.get(f"/assets/{asset_id}", headers=auth_headers).json()[
            "current_price"
        ]
        == 99.0
    )

    deleted = integration_client.delete(
        f"/assets/{asset_id}/prices/{TODAY}", headers=auth_headers
    )

    assert deleted.status_code == 204
    detail = integration_client.get(f"/assets/{asset_id}", headers=auth_headers).json()
    assert (detail["current_price"], detail["price_source"]) == (20.0, "yahoo")
    missing = integration_client.delete(
        f"/assets/{asset_id}/prices/{TODAY}", headers=auth_headers
    )
    assert (missing.status_code, missing.json()["code"]) == (404, "PRICE_NOT_FOUND")


def test_a_refresh_is_idempotent_per_day_and_manual_outranks_it(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    asset: dict[str, object],
    integration_session: Session,
    fake_provider: FakeMarketDataProvider,
) -> None:
    asset_id = asset["id"]
    orm_asset = integration_session.get(Asset, asset_id)
    assert orm_asset is not None
    fake_provider.quotes[orm_asset.ticker] = make_quote(
        orm_asset.ticker, current_price=Decimal("20")
    )
    market_data = assets_wiring.build_market_data_service(integration_session)

    market_data.refresh_asset_prices([orm_asset])
    fake_provider.quotes[orm_asset.ticker] = make_quote(
        orm_asset.ticker, current_price=Decimal("21")
    )
    market_data.refresh_asset_prices([orm_asset])

    provider_rows = _prices(integration_client, auth_headers, asset_id, source="yahoo")[
        "items"
    ]
    assert [(i["close"], i["is_synthetic"]) for i in provider_rows] == [(21.0, True)]

    integration_client.put(
        f"/assets/{asset_id}/prices/{TODAY}", headers=auth_headers, json={"close": 50}
    )
    market_data.refresh_asset_prices([orm_asset])

    effective = _prices(integration_client, auth_headers, asset_id)["items"]
    assert [(i["close"], i["source"]) for i in effective] == [(50.0, "manual")]
    assert orm_asset.current_price == Decimal("50")


def test_editing_the_price_of_an_asset_writes_a_manual_close(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    asset: dict[str, object],
) -> None:
    asset_id = asset["id"]

    patched = integration_client.patch(
        f"/assets/{asset_id}", headers=auth_headers, json={"current_price": 33.25}
    )

    assert patched.status_code == 200
    assert patched.json()["current_price"] == 33.25
    assert patched.json()["price_source"] == "manual"
    items = _prices(integration_client, auth_headers, asset_id)["items"]
    assert [(i["price_date"], i["close"]) for i in items] == [(str(TODAY), 33.25)]


def test_manual_price_validation_errors_carry_their_codes(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    asset: dict[str, object],
    seeded_currency: Currency,
) -> None:
    asset_id = asset["id"]
    tomorrow = TODAY + timedelta(days=1)

    future = integration_client.put(
        f"/assets/{asset_id}/prices/{tomorrow}", headers=auth_headers, json={"close": 1}
    )
    wrong_currency = integration_client.put(
        f"/assets/{asset_id}/prices/{TODAY}",
        headers=auth_headers,
        json={"close": 1, "currency_id": seeded_currency.id + 1000},
    )
    unknown = integration_client.put(
        f"/assets/999999999/prices/{TODAY}", headers=auth_headers, json={"close": 1}
    )
    bad_range = integration_client.get(
        f"/assets/{asset_id}/prices",
        headers=auth_headers,
        params={"from": str(TODAY), "to": str(YESTERDAY)},
    )

    assert (future.status_code, future.json()["code"]) == (400, "DATE_IN_FUTURE")
    assert (wrong_currency.status_code, wrong_currency.json()["code"]) == (
        400,
        "PRICE_CURRENCY_MISMATCH",
    )
    assert (unknown.status_code, unknown.json()["code"]) == (404, "ASSET_NOT_FOUND")
    assert (bad_range.status_code, bad_range.json()["code"]) == (
        400,
        "INVALID_DATE_RANGE",
    )


def test_an_archived_asset_takes_no_prices_and_is_not_refreshed(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    asset: dict[str, object],
    integration_session: Session,
    fake_provider: FakeMarketDataProvider,
) -> None:
    asset_id = asset["id"]
    integration_client.post(f"/assets/{asset_id}/archive", headers=auth_headers)

    refused = integration_client.put(
        f"/assets/{asset_id}/prices/{TODAY}", headers=auth_headers, json={"close": 1}
    )
    price_edit = integration_client.patch(
        f"/assets/{asset_id}", headers=auth_headers, json={"current_price": 2}
    )
    orm_asset = integration_session.get(Asset, asset_id)
    assert orm_asset is not None
    fake_provider.quotes[orm_asset.ticker] = make_quote(orm_asset.ticker)
    refreshed = assets_wiring.build_market_data_service(
        integration_session
    ).refresh_asset_prices([orm_asset])

    assert (refused.status_code, refused.json()["code"]) == (409, "ASSET_ARCHIVED")
    assert price_edit.status_code == 409
    assert refreshed == 0
    assert fake_provider.calls == []


def test_identifiers_are_validated_normalized_and_unique(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency: Currency,
) -> None:
    asset_class = integration_client.post(
        "/assets/asset-classes",
        headers=auth_headers,
        json={"name": integration_data.value("c")[:20]},
    ).json()

    def create(ticker: str, **extra: object):
        return integration_client.post(
            "/assets/",
            headers=auth_headers,
            json={
                "ticker": integration_data.value(ticker)[:20],
                "name": "Identified",
                "asset_class_id": asset_class["id"],
                "currency_id": seeded_currency.id,
                **extra,
            },
        )

    # An ISIN no real-world test data can collide with: derive a valid one.
    isin = "XS0000000009"
    created = create("a", isin=isin.lower(), mic="xwar", country="pl", asset_type="etf")
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["isin"], body["mic"], body["country"], body["asset_type"]) == (
        isin,
        "XWAR",
        "PL",
        "etf",
    )

    duplicate = create("b", isin=isin)
    assert (duplicate.status_code, duplicate.json()["code"]) == (
        409,
        "ASSET_ALREADY_EXISTS",
    )
    assert create("c", isin="XS0000000008").status_code == 422
    assert create("d", asset_type="stonk").status_code == 422

    by_isin = integration_client.get(
        "/assets/", headers=auth_headers, params={"search": isin}
    )
    assert [a["id"] for a in by_isin.json()] == [body["id"]]
    filtered = integration_client.get(
        "/assets/",
        headers=auth_headers,
        params={"asset_type": "etf", "country": "pl", "search": isin},
    )
    assert len(filtered.json()) == 1

    cleared = integration_client.patch(
        f"/assets/{body['id']}", headers=auth_headers, json={"isin": None}
    )
    assert cleared.status_code == 200
    assert cleared.json()["isin"] is None
    assert create("e", isin=isin).status_code == 201


def test_refresh_prices_endpoint_accepts_known_active_assets(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    asset: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queued: list[list[int]] = []
    monkeypatch.setattr(entrypoints, "refresh_prices", lambda ids: queued.append(ids))

    accepted = integration_client.post(
        "/assets/refresh-prices",
        headers=auth_headers,
        json={"asset_ids": [asset["id"]]},
    )
    unknown = integration_client.post(
        "/assets/refresh-prices", headers=auth_headers, json={"asset_ids": [999999999]}
    )

    assert accepted.status_code == 202
    assert accepted.json() == {"accepted": [asset["id"]]}
    assert queued == [[asset["id"]]]
    assert unknown.status_code == 404


# --- exchange rates ---


def _currency_id(client: TestClient, headers: dict[str, str], code: str) -> int:
    for item in client.get("/assets/currencies", headers=headers).json():
        if item["code"] == code:
            return int(item["id"])
    raise AssertionError(f"currency {code} is not seeded")


def test_a_manual_rate_resolves_directly_inversely_and_updates_the_cache(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    currency_codes: CurrencyCodes,
) -> None:
    code = currency_codes.new()
    usd = _currency_id(integration_client, auth_headers, "USD")
    created = integration_client.post(
        "/assets/currencies", headers=auth_headers, json={"code": code}
    ).json()

    put = integration_client.put(
        "/assets/fx-rates",
        headers=auth_headers,
        json={
            "from_currency_id": usd,
            "to_currency_id": created["id"],
            "rate_date": str(TODAY),
            "rate": 4,
        },
    )

    assert put.status_code == 200, put.text
    assert put.json()["source"] == "manual"
    inverse = integration_client.get(
        "/assets/currencies/rate",
        headers=auth_headers,
        params={"from_currency": code, "to_currency": "USD"},
    ).json()
    assert (inverse["via"], inverse["rate"], inverse["source"]) == (
        "inverse",
        0.25,
        "manual",
    )
    direct = integration_client.get(
        "/assets/currencies/rate",
        headers=auth_headers,
        params={"from_currency": "USD", "to_currency": code.lower()},
    ).json()
    assert (direct["via"], direct["rate"]) == ("direct", 4.0)
    # The cached `exchange_rate` (USD per unit) follows the history.
    cached = integration_client.get(
        f"/assets/currencies/{created['id']}", headers=auth_headers
    ).json()
    assert cached["exchange_rate"] == 0.25


def test_a_missing_or_unknown_rate_has_a_code(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    currency_codes: CurrencyCodes,
) -> None:
    code = currency_codes.new()
    integration_client.post(
        "/assets/currencies", headers=auth_headers, json={"code": code}
    )

    missing = integration_client.get(
        "/assets/currencies/rate",
        headers=auth_headers,
        params={"from_currency": code, "to_currency": "USD"},
    )
    unknown = integration_client.get(
        "/assets/currencies/rate",
        headers=auth_headers,
        params={"from_currency": "ZZZ", "to_currency": "USD"},
    )
    same = integration_client.get(
        "/assets/currencies/rate",
        headers=auth_headers,
        params={"from_currency": "USD", "to_currency": "USD"},
    )

    assert (missing.status_code, missing.json()["code"]) == (404, "RATE_MISSING")
    assert (unknown.status_code, unknown.json()["code"]) == (404, "CURRENCY_NOT_FOUND")
    assert (same.json()["via"], same.json()["rate"]) == ("identity", 1.0)


def test_the_rate_history_is_filtered_by_range_and_source(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    currency_codes: CurrencyCodes,
) -> None:
    code = currency_codes.new()
    usd = _currency_id(integration_client, auth_headers, "USD")
    created = integration_client.post(
        "/assets/currencies", headers=auth_headers, json={"code": code}
    ).json()
    for offset, rate in ((5, 3.9), (1, 4.1)):
        integration_client.put(
            "/assets/fx-rates",
            headers=auth_headers,
            json={
                "from_currency_id": created["id"],
                "to_currency_id": usd,
                "rate_date": str(TODAY - timedelta(days=offset)),
                "rate": rate,
            },
        )

    everything = integration_client.get(
        "/assets/fx-rates",
        headers=auth_headers,
        params={"from_currency": code, "to_currency": "USD"},
    ).json()["items"]
    recent = integration_client.get(
        "/assets/fx-rates",
        headers=auth_headers,
        params={
            "from_currency": code,
            "to_currency": "USD",
            "from": str(TODAY - timedelta(days=2)),
        },
    ).json()["items"]
    other_source = integration_client.get(
        "/assets/fx-rates",
        headers=auth_headers,
        params={"from_currency": code, "to_currency": "USD", "source": "yahoo"},
    ).json()["items"]

    assert [i["rate"] for i in everything] == [3.9, 4.1]
    assert [i["rate"] for i in recent] == [4.1]
    assert other_source == []


def test_a_currency_created_with_a_rate_records_it_and_deleting_it_removes_the_rates(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    currency_codes: CurrencyCodes,
    integration_session: Session,
) -> None:
    code = currency_codes.new()

    created = integration_client.post(
        "/assets/currencies",
        headers=auth_headers,
        json={"code": code, "exchange_rate": 4.25},
    ).json()
    history = integration_client.get(
        "/assets/fx-rates",
        headers=auth_headers,
        params={"from_currency": code, "to_currency": "USD"},
    ).json()["items"]

    assert [(i["rate"], i["source"]) for i in history] == [(4.25, "manual")]
    assert history[0]["rate_date"] == str(TODAY)

    updated = integration_client.patch(
        f"/assets/currencies/{created['id']}",
        headers=auth_headers,
        json={"exchange_rate": 4.5},
    )
    assert updated.json()["exchange_rate"] == 4.5
    after = integration_client.get(
        "/assets/fx-rates",
        headers=auth_headers,
        params={"from_currency": code, "to_currency": "USD"},
    ).json()["items"]
    assert [i["rate"] for i in after] == [4.5]  # same day, same source: replaced

    deleted = integration_client.delete(
        f"/assets/currencies/{created['id']}", headers=auth_headers
    )
    assert deleted.status_code == 204
    left = integration_session.execute(
        select(FxRate).where(FxRate.from_currency_id == created["id"])
    ).all()
    assert left == []


def test_a_provider_refresh_writes_history_and_keeps_the_cache_in_step(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    currency_codes: CurrencyCodes,
    integration_session: Session,
    fake_provider: FakeMarketDataProvider,
) -> None:
    code = currency_codes.new()
    created = integration_client.post(
        "/assets/currencies", headers=auth_headers, json={"code": code}
    ).json()
    fake_provider.rates[(code, "USD")] = Decimal("0.5")
    market_data = assets_wiring.build_market_data_service(integration_session)

    market_data.refresh_currency_rates()
    market_data.refresh_currency_rates()  # a second run on the same day

    rows = integration_session.execute(
        select(FxRate).where(FxRate.from_currency_id == created["id"])
    ).scalars()
    stored = list(rows)
    assert [(r.source, r.rate, r.is_synthetic) for r in stored] == [
        ("yahoo", Decimal("0.5"), True)
    ]
    cached = integration_client.get(
        f"/assets/currencies/{created['id']}", headers=auth_headers
    ).json()
    assert cached["exchange_rate"] == 0.5


# --- backfill ---


def test_backfill_seeds_history_from_the_caches_once(
    integration_session: Session,
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    currency_codes: CurrencyCodes,
) -> None:
    code = currency_codes.new()
    integration_session.add(Currency(code=code, exchange_rate=Decimal("2.5")))
    integration_session.flush()
    backfill = assets_wiring.build_history_backfill_service(integration_session)
    # Leave only the data this test controls: clear history written by other rows.
    integration_session.query(AssetPrice).delete()
    integration_session.query(FxRate).delete()

    first = backfill.backfill()
    second = backfill.backfill()

    assert first.prices >= 1 and first.rates >= 1
    assert (second.prices, second.rates) == (0, 0)
    legacy = integration_session.execute(
        select(FxRate)
        .join(Currency, FxRate.from_currency_id == Currency.id)
        .where(Currency.code == code)
    ).scalar_one()
    assert (legacy.source, legacy.rate, legacy.is_synthetic) == (
        "legacy",
        Decimal("2.5"),
        True,
    )
    priced = integration_session.execute(select(AssetPrice)).scalars().all()
    assert priced
    assert {p.source for p in priced} == {"legacy"}
    # Legacy rows rank last: any real observation of the same day outranks them.
    detail = integration_client.get(
        f"/assets/{priced[0].asset_id}", headers=auth_headers
    ).json()
    assert detail["price_source"] == "legacy"
