from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.market_data import MarketDataUnavailableError
from app.modules.assets.exceptions import (
    AssetAlreadyExistsError,
    AssetInUseError,
    AssetNotFoundError,
    AssetNotFoundOnProviderError,
    UnknownAssetClassError,
    UnknownCurrencyError,
)
from app.modules.assets.schemas.assets import (
    AssetCreateRequest,
    AssetFromProviderRequest,
    AssetUpdateRequest,
)
from app.modules.assets.services.assets import AssetService
from app.modules.assets.services.market_data import MarketDataService
from app.modules.assets.tests.fakes import FakeMarketDataProvider, make_quote


def _integrity_error() -> IntegrityError:
    return IntegrityError("INSERT ...", {}, Exception("constraint"))


def _detail_asset(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": 1,
        "ticker": "AAPL",
        "name": "Apple",
        "asset_class": SimpleNamespace(id=1, name="Stock"),
        "currency": SimpleNamespace(
            id=1, code="USD", exchange_rate=Decimal("1"), base_currency_id=None
        ),
        "current_price": Decimal("190.5"),
        "exchange": "NMS",
        "sector": "Technology",
        "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def provider() -> FakeMarketDataProvider:
    return FakeMarketDataProvider()


@pytest.fixture
def asset_classes() -> MagicMock:
    return MagicMock()


@pytest.fixture
def currencies() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(
    asset_repo: MagicMock,
    currency_repo: MagicMock,
    asset_classes: MagicMock,
    currencies: MagicMock,
    provider: FakeMarketDataProvider,
) -> AssetService:
    market_data = MarketDataService(asset_repo, currency_repo, provider)
    return AssetService(asset_repo, asset_classes, currencies, market_data)


def _create_request(**overrides: object) -> AssetCreateRequest:
    payload: dict[str, object] = {
        "ticker": " aapl ",
        "name": "Apple",
        "asset_class_id": 1,
        "currency_id": 2,
        "current_price": "190.5",
    }
    payload.update(overrides)
    return AssetCreateRequest.model_validate(payload)


# --- create ---


def test_create_normalizes_ticker_and_commits(
    service: AssetService, asset_repo: MagicMock, session: MagicMock
) -> None:
    asset_repo.find_by_ticker.return_value = None
    created = SimpleNamespace(id=1)
    asset_repo.create.return_value = created

    assert service.create(_create_request()) is created

    asset_repo.find_by_ticker.assert_called_once_with("AAPL")
    asset_repo.create.assert_called_once_with(
        ticker="AAPL",
        name="Apple",
        asset_class_id=1,
        currency_id=2,
        current_price=Decimal("190.5"),
        exchange="",
        sector="",
    )
    session.commit.assert_called_once()


def test_create_rejects_duplicate_ticker(
    service: AssetService, asset_repo: MagicMock, session: MagicMock
) -> None:
    asset_repo.find_by_ticker.return_value = SimpleNamespace(id=1)

    with pytest.raises(AssetAlreadyExistsError) as exc_info:
        service.create(_create_request())

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "ASSET_ALREADY_EXISTS"
    asset_repo.create.assert_not_called()
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_create_rejects_unknown_asset_class(
    service: AssetService,
    asset_repo: MagicMock,
    asset_classes: MagicMock,
    session: MagicMock,
) -> None:
    asset_repo.find_by_ticker.return_value = None
    asset_classes.find_by_id.return_value = None

    with pytest.raises(UnknownAssetClassError) as exc_info:
        service.create(_create_request())

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "ASSET_CLASS_NOT_FOUND"
    session.commit.assert_not_called()


def test_create_rejects_unknown_currency(
    service: AssetService, asset_repo: MagicMock, currencies: MagicMock
) -> None:
    asset_repo.find_by_ticker.return_value = None
    currencies.find_by_id.return_value = None

    with pytest.raises(UnknownCurrencyError) as exc_info:
        service.create(_create_request())

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "CURRENCY_NOT_FOUND"


def test_create_translates_a_lost_race_on_the_unique_ticker(
    service: AssetService, asset_repo: MagicMock, session: MagicMock
) -> None:
    asset_repo.find_by_ticker.side_effect = [None, SimpleNamespace(id=8)]
    asset_repo.create.side_effect = _integrity_error()

    with pytest.raises(AssetAlreadyExistsError) as exc_info:
        service.create(_create_request())

    assert isinstance(exc_info.value.__cause__, IntegrityError)
    session.rollback.assert_called_once()


# --- update / delete / reads ---


def test_update_sets_only_given_fields_and_normalizes_ticker(
    service: AssetService, asset_repo: MagicMock, session: MagicMock
) -> None:
    asset = SimpleNamespace(id=1, ticker="AAPL", name="Apple", sector="Tech")
    asset_repo.get_by_id.return_value = asset
    asset_repo.find_by_ticker.return_value = None
    asset_repo.update.side_effect = lambda entity: entity

    service.update(1, AssetUpdateRequest(ticker=" aapl.us ", name="Apple Inc."))

    assert (asset.ticker, asset.name, asset.sector) == ("AAPL.US", "Apple Inc.", "Tech")
    session.commit.assert_called_once()


def test_update_rejects_ticker_of_another_asset(
    service: AssetService, asset_repo: MagicMock, session: MagicMock
) -> None:
    asset_repo.get_by_id.return_value = SimpleNamespace(id=1, ticker="AAPL")
    asset_repo.find_by_ticker.return_value = SimpleNamespace(id=2, ticker="MSFT")

    with pytest.raises(AssetAlreadyExistsError):
        service.update(1, AssetUpdateRequest(ticker="msft"))

    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_update_rejects_unknown_asset_class(
    service: AssetService, asset_repo: MagicMock, asset_classes: MagicMock
) -> None:
    asset_repo.get_by_id.return_value = SimpleNamespace(id=1)
    asset_classes.find_by_id.return_value = None

    with pytest.raises(UnknownAssetClassError):
        service.update(1, AssetUpdateRequest(asset_class_id=99))


def test_update_request_rejects_null_for_not_null_columns() -> None:
    with pytest.raises(ValueError, match="name cannot be null"):
        AssetUpdateRequest.model_validate({"name": None})


def test_delete_of_referenced_asset_is_in_use(
    service: AssetService, asset_repo: MagicMock, session: MagicMock
) -> None:
    asset_repo.get_by_id.return_value = SimpleNamespace(id=1)
    asset_repo.delete.side_effect = _integrity_error()

    with pytest.raises(AssetInUseError) as exc_info:
        service.delete(1)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "ASSET_IN_USE"
    session.rollback.assert_called_once()


def test_get_by_id_propagates_not_found(
    service: AssetService, asset_repo: MagicMock
) -> None:
    asset_repo.get_by_id.side_effect = AssetNotFoundError

    with pytest.raises(AssetNotFoundError) as exc_info:
        service.get_by_id(5)

    assert exc_info.value.code == "ASSET_NOT_FOUND"


def test_find_by_id_returns_none_when_missing(
    service: AssetService, asset_repo: MagicMock
) -> None:
    asset_repo.find_by_id.return_value = None

    assert service.find_by_id(5) is None


def test_find_by_ticker_normalizes_the_lookup_key(
    service: AssetService, asset_repo: MagicMock
) -> None:
    found = SimpleNamespace(id=1)
    asset_repo.find_by_ticker.return_value = found

    assert service.find_by_ticker("  cdr.wa ") is found
    asset_repo.find_by_ticker.assert_called_once_with("CDR.WA")


# --- get_or_create_by_ticker (no-commit core) ---


def test_get_or_create_by_ticker_returns_existing_without_writing(
    service: AssetService,
    asset_repo: MagicMock,
    asset_classes: MagicMock,
    session: MagicMock,
) -> None:
    existing = SimpleNamespace(id=1, ticker="CDR")
    asset_repo.find_by_ticker.return_value = existing

    result = service.get_or_create_by_ticker(
        "cdr", asset_class_name="Stock", fallback_currency_id=1
    )

    assert result is existing
    asset_repo.create.assert_not_called()
    asset_classes.get_or_create_by_name.assert_not_called()
    session.commit.assert_not_called()


def test_get_or_create_by_ticker_creates_without_committing(
    service: AssetService,
    asset_repo: MagicMock,
    asset_classes: MagicMock,
    session: MagicMock,
) -> None:
    asset_repo.find_by_ticker.return_value = None
    asset_classes.get_or_create_by_name.return_value = SimpleNamespace(id=7)
    created = SimpleNamespace(id=11)
    asset_repo.create.return_value = created

    result = service.get_or_create_by_ticker(
        " cdr ", asset_class_name="Stock", fallback_currency_id=3
    )

    assert result is created
    asset_classes.get_or_create_by_name.assert_called_once_with("Stock")
    asset_repo.create.assert_called_once_with(
        ticker="CDR", name="CDR", asset_class_id=7, currency_id=3
    )
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_get_or_create_by_ticker_rejects_unknown_currency(
    service: AssetService, asset_repo: MagicMock, currencies: MagicMock
) -> None:
    asset_repo.find_by_ticker.return_value = None
    currencies.find_by_id.return_value = None

    with pytest.raises(UnknownCurrencyError):
        service.get_or_create_by_ticker(
            "CDR", asset_class_name="Stock", fallback_currency_id=9
        )

    asset_repo.create.assert_not_called()


def test_get_or_create_by_ticker_uses_the_provider_quote_currency(
    service: AssetService,
    asset_repo: MagicMock,
    asset_classes: MagicMock,
    currencies: MagicMock,
    provider: FakeMarketDataProvider,
) -> None:
    asset_repo.find_by_ticker.return_value = None
    asset_classes.get_or_create_by_name.return_value = SimpleNamespace(id=7)
    currencies.get_or_create_by_code.return_value = SimpleNamespace(id=5)
    provider.quotes["AAPL"] = make_quote("AAPL", currency="USD")

    service.get_or_create_by_ticker(
        "aapl", asset_class_name="Stock", fallback_currency_id=3
    )

    currencies.get_or_create_by_code.assert_called_once_with("USD")
    asset_repo.create.assert_called_once_with(
        ticker="AAPL", name="AAPL", asset_class_id=7, currency_id=5
    )


def test_get_or_create_by_ticker_falls_back_when_the_provider_is_down(
    service: AssetService,
    asset_repo: MagicMock,
    asset_classes: MagicMock,
    provider: FakeMarketDataProvider,
) -> None:
    asset_repo.find_by_ticker.return_value = None
    asset_classes.get_or_create_by_name.return_value = SimpleNamespace(id=7)
    provider.failing.add("AAPL")

    service.get_or_create_by_ticker(
        "AAPL", asset_class_name="Stock", fallback_currency_id=3
    )

    asset_repo.create.assert_called_once_with(
        ticker="AAPL", name="AAPL", asset_class_id=7, currency_id=3
    )


# --- create_from_provider ---


@pytest.mark.parametrize(
    ("quote_type", "class_name"),
    [
        ("ETF", "ETF"),
        ("CRYPTOCURRENCY", "Crypto"),
        ("CRYPTO", "Crypto"),
        ("MUTUALFUND", "Mutual Fund"),
        ("EQUITY", "Stock"),
        ("", "Stock"),
        ("FUTURE", "Stock"),
    ],
)
def test_create_from_provider_maps_quote_type_to_asset_class(
    service: AssetService,
    asset_repo: MagicMock,
    asset_classes: MagicMock,
    provider: FakeMarketDataProvider,
    quote_type: str,
    class_name: str,
) -> None:
    asset_repo.find_by_ticker.return_value = None
    provider.quotes["VWCE"] = make_quote("VWCE", quote_type=quote_type)

    service.create_from_provider(AssetFromProviderRequest(ticker="vwce"))

    asset_classes.get_or_create_by_name.assert_called_once_with(class_name)


def test_create_from_provider_builds_asset_from_quote_and_commits(
    service: AssetService,
    asset_repo: MagicMock,
    asset_classes: MagicMock,
    currencies: MagicMock,
    provider: FakeMarketDataProvider,
    session: MagicMock,
) -> None:
    asset_repo.find_by_ticker.return_value = None
    asset_classes.get_or_create_by_name.return_value = SimpleNamespace(id=4)
    currencies.get_or_create_by_code.return_value = SimpleNamespace(id=5)
    provider.quotes["AAPL"] = make_quote(
        "AAPL", currency="", current_price=None, regular_market_price=Decimal("201")
    )
    created = SimpleNamespace(id=1)
    asset_repo.create.return_value = created

    assert service.create_from_provider(AssetFromProviderRequest(ticker=" aapl ")) is (
        created
    )

    currencies.get_or_create_by_code.assert_called_once_with("USD")
    asset_repo.create.assert_called_once_with(
        ticker="AAPL",
        name="Apple Inc.",
        asset_class_id=4,
        currency_id=5,
        current_price=Decimal("201"),
        exchange="NMS",
        sector="Technology",
    )
    session.commit.assert_called_once()


def test_create_from_provider_falls_back_to_ticker_name_and_zero_price(
    service: AssetService, asset_repo: MagicMock, provider: FakeMarketDataProvider
) -> None:
    asset_repo.find_by_ticker.return_value = None
    provider.quotes["XYZ"] = make_quote(
        "XYZ",
        name="",
        current_price=None,
        regular_market_price=None,
        previous_close=None,
    )

    service.create_from_provider(AssetFromProviderRequest(ticker="XYZ"))

    kwargs = asset_repo.create.call_args.kwargs
    assert kwargs["name"] == "XYZ"
    assert kwargs["current_price"] == Decimal("0")


def test_create_from_provider_uses_explicit_class_and_currency(
    service: AssetService,
    asset_repo: MagicMock,
    asset_classes: MagicMock,
    currencies: MagicMock,
    provider: FakeMarketDataProvider,
) -> None:
    asset_repo.find_by_ticker.return_value = None
    provider.quotes["AAPL"] = make_quote()

    service.create_from_provider(
        AssetFromProviderRequest(ticker="AAPL", asset_class_id=2, currency_id=3)
    )

    asset_classes.get_or_create_by_name.assert_not_called()
    currencies.get_or_create_by_code.assert_not_called()
    kwargs = asset_repo.create.call_args.kwargs
    assert (kwargs["asset_class_id"], kwargs["currency_id"]) == (2, 3)


def test_create_from_provider_rejects_unknown_explicit_currency(
    service: AssetService,
    asset_repo: MagicMock,
    currencies: MagicMock,
    provider: FakeMarketDataProvider,
    session: MagicMock,
) -> None:
    asset_repo.find_by_ticker.return_value = None
    currencies.find_by_id.return_value = None
    provider.quotes["AAPL"] = make_quote()

    with pytest.raises(UnknownCurrencyError):
        service.create_from_provider(
            AssetFromProviderRequest(ticker="AAPL", currency_id=3)
        )

    asset_repo.create.assert_not_called()
    session.commit.assert_not_called()


def test_create_from_provider_rejects_known_ticker_before_calling_provider(
    service: AssetService, asset_repo: MagicMock, provider: FakeMarketDataProvider
) -> None:
    asset_repo.find_by_ticker.return_value = SimpleNamespace(id=1)

    with pytest.raises(AssetAlreadyExistsError):
        service.create_from_provider(AssetFromProviderRequest(ticker="AAPL"))

    assert provider.calls == []


def test_create_from_provider_reports_ticker_unknown_to_provider(
    service: AssetService, asset_repo: MagicMock
) -> None:
    asset_repo.find_by_ticker.return_value = None

    with pytest.raises(AssetNotFoundOnProviderError) as exc_info:
        service.create_from_provider(AssetFromProviderRequest(ticker="NOPE"))

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "ASSET_NOT_FOUND_ON_PROVIDER"
    asset_repo.create.assert_not_called()


def test_create_from_provider_propagates_provider_outage(
    service: AssetService, asset_repo: MagicMock, provider: FakeMarketDataProvider
) -> None:
    asset_repo.find_by_ticker.return_value = None
    provider.failing.add("AAPL")

    with pytest.raises(MarketDataUnavailableError) as exc_info:
        service.create_from_provider(AssetFromProviderRequest(ticker="AAPL"))

    assert exc_info.value.status_code == 502


# --- search_local_and_provider ---


def test_search_combines_local_assets_with_unknown_provider_hits(
    service: AssetService, asset_repo: MagicMock, provider: FakeMarketDataProvider
) -> None:
    asset_repo.list_all.return_value = [_detail_asset(ticker="MSFT")]
    asset_repo.find_by_ticker.side_effect = lambda ticker: (
        _detail_asset(ticker=ticker) if ticker == "MSFT" else None
    )
    provider.quotes["MSFT"] = make_quote("MSFT", name="Microsoft")

    known = service.search_local_and_provider("msft")

    asset_repo.list_all.assert_called_once_with(search="msft", limit=10)
    assert [a.ticker for a in known.local] == ["MSFT"]
    assert known.yahoo == []

    provider.quotes["AAPL"] = make_quote("AAPL", quote_type="ETF")
    asset_repo.list_all.return_value = []

    found = service.search_local_and_provider("aapl")

    assert found.local == []
    assert [(q.symbol, q.type, q.currency) for q in found.yahoo] == [
        ("AAPL", "ETF", "USD")
    ]


def test_search_with_picker_format_looks_up_the_ticker_part_locally(
    service: AssetService, asset_repo: MagicMock, provider: FakeMarketDataProvider
) -> None:
    asset_repo.list_all.return_value = [_detail_asset(ticker="MSFT")]
    asset_repo.find_by_ticker.return_value = _detail_asset(ticker="MSFT")
    provider.quotes["MSFT"] = make_quote("MSFT", name="Microsoft")

    found = service.search_local_and_provider("MSFT - Microsoft Corp")

    asset_repo.list_all.assert_called_once_with(search="MSFT", limit=10)
    assert [a.ticker for a in found.local] == ["MSFT"]
    # Already stored locally, even if the capped local list had missed it.
    assert found.yahoo == []
