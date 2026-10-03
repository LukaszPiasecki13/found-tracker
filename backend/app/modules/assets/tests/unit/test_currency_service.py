from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.assets.exceptions import (
    CurrencyAlreadyExistsError,
    CurrencyInUseError,
    CurrencyNotFoundError,
    UnknownBaseCurrencyError,
)
from app.modules.assets.schemas.currencies import (
    CurrencyCreateRequest,
    CurrencyUpdateRequest,
)
from app.modules.assets.services.currencies import CurrencyService


def _integrity_error() -> IntegrityError:
    return IntegrityError("INSERT ...", {}, Exception("constraint"))


@pytest.fixture
def fx_rates() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(currency_repo: MagicMock, fx_rates: MagicMock) -> CurrencyService:
    return CurrencyService(currency_repo, fx_rates)


def test_create_uppercases_the_code(
    service: CurrencyService, currency_repo: MagicMock, session: MagicMock
) -> None:
    currency_repo.find_by_code.return_value = None
    created = SimpleNamespace(id=1, code="EUR")
    currency_repo.create.return_value = created

    result = service.create(
        CurrencyCreateRequest(code="eur", exchange_rate=Decimal("4.25"))
    )

    assert result is created
    currency_repo.find_by_code.assert_called_once_with("EUR")
    currency_repo.create.assert_called_once_with(
        code="EUR", exchange_rate=Decimal("4.25"), base_currency_id=None
    )
    session.commit.assert_called_once()


def test_create_rejects_duplicate_code(
    service: CurrencyService, currency_repo: MagicMock, session: MagicMock
) -> None:
    currency_repo.find_by_code.return_value = SimpleNamespace(id=1, code="EUR")

    with pytest.raises(CurrencyAlreadyExistsError) as exc_info:
        service.create(CurrencyCreateRequest(code="eur"))

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "CURRENCY_ALREADY_EXISTS"
    currency_repo.create.assert_not_called()
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_create_rejects_unknown_base_currency(
    service: CurrencyService, currency_repo: MagicMock, session: MagicMock
) -> None:
    currency_repo.find_by_code.return_value = None
    currency_repo.find_by_id.return_value = None

    with pytest.raises(UnknownBaseCurrencyError) as exc_info:
        service.create(CurrencyCreateRequest(code="EUR", base_currency_id=99))

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "BASE_CURRENCY_NOT_FOUND"
    currency_repo.create.assert_not_called()
    session.commit.assert_not_called()


def test_create_translates_a_lost_race_on_the_unique_code(
    service: CurrencyService, currency_repo: MagicMock, session: MagicMock
) -> None:
    currency_repo.find_by_code.side_effect = [None, SimpleNamespace(id=5)]
    currency_repo.create.side_effect = _integrity_error()

    with pytest.raises(CurrencyAlreadyExistsError):
        service.create(CurrencyCreateRequest(code="EUR"))

    session.rollback.assert_called_once()


def test_update_uppercases_code_and_sets_only_given_fields(
    service: CurrencyService, currency_repo: MagicMock, session: MagicMock
) -> None:
    currency = SimpleNamespace(
        id=1, code="EUR", exchange_rate=Decimal("4"), base_currency_id=2
    )
    currency_repo.get_by_id.return_value = currency
    currency_repo.find_by_code.return_value = None
    currency_repo.update.side_effect = lambda entity: entity

    service.update(1, CurrencyUpdateRequest(code="chf"))

    assert currency.code == "CHF"
    assert currency.exchange_rate == Decimal("4")
    assert currency.base_currency_id == 2
    session.commit.assert_called_once()


def test_update_with_null_base_currency_clears_it(
    service: CurrencyService, currency_repo: MagicMock
) -> None:
    currency = SimpleNamespace(id=1, code="EUR", base_currency_id=2)
    currency_repo.get_by_id.return_value = currency
    currency_repo.update.side_effect = lambda entity: entity

    service.update(1, CurrencyUpdateRequest(base_currency_id=None))

    assert currency.base_currency_id is None
    currency_repo.find_by_id.assert_not_called()


def test_update_rejects_code_of_another_currency(
    service: CurrencyService, currency_repo: MagicMock, session: MagicMock
) -> None:
    currency_repo.get_by_id.return_value = SimpleNamespace(id=1, code="EUR")
    currency_repo.find_by_code.return_value = SimpleNamespace(id=2, code="USD")

    with pytest.raises(CurrencyAlreadyExistsError):
        service.update(1, CurrencyUpdateRequest(code="usd"))

    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_update_rejects_unknown_base_currency(
    service: CurrencyService, currency_repo: MagicMock
) -> None:
    currency_repo.get_by_id.return_value = SimpleNamespace(id=1, code="EUR")
    currency_repo.find_by_id.return_value = None

    with pytest.raises(UnknownBaseCurrencyError):
        service.update(1, CurrencyUpdateRequest(base_currency_id=42))


def test_update_request_rejects_null_for_required_fields() -> None:
    with pytest.raises(ValueError, match="exchange_rate cannot be null"):
        CurrencyUpdateRequest.model_validate({"exchange_rate": None})


def test_delete_of_referenced_currency_is_in_use(
    service: CurrencyService, currency_repo: MagicMock, session: MagicMock
) -> None:
    currency_repo.get_by_id.return_value = SimpleNamespace(id=1)
    currency_repo.delete.side_effect = _integrity_error()

    with pytest.raises(CurrencyInUseError) as exc_info:
        service.delete(1)

    assert exc_info.value.code == "CURRENCY_IN_USE"
    session.rollback.assert_called_once()


def test_get_by_id_propagates_not_found(
    service: CurrencyService, currency_repo: MagicMock
) -> None:
    currency_repo.get_by_id.side_effect = CurrencyNotFoundError

    with pytest.raises(CurrencyNotFoundError) as exc_info:
        service.get_by_id(7)

    assert exc_info.value.status_code == 404


def test_find_by_id_returns_none_when_missing(
    service: CurrencyService, currency_repo: MagicMock
) -> None:
    currency_repo.find_by_id.return_value = None

    assert service.find_by_id(7) is None


def test_get_or_create_by_code_normalizes_and_does_not_commit(
    service: CurrencyService, currency_repo: MagicMock, session: MagicMock
) -> None:
    currency_repo.find_by_code.return_value = None
    created = SimpleNamespace(id=3, code="GBP")
    currency_repo.create.return_value = created

    assert service.get_or_create_by_code(" gbp ") is created

    currency_repo.find_by_code.assert_called_once_with("GBP")
    currency_repo.create.assert_called_once_with(code="GBP")
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {"code": "EURO"},
        {"code": "E1R"},
        {"code": "EUR", "exchange_rate": 0},
        {"code": "EUR", "exchange_rate": 1_000_000_000},
        {"code": "EUR", "symbol": "€"},
    ],
)
def test_create_request_validates_shape(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        CurrencyCreateRequest.model_validate(payload)


# --- manual exchange rates enter the history (ADR-0015) ---


def test_create_with_an_explicit_rate_records_it_as_a_manual_rate(
    service: CurrencyService, currency_repo: MagicMock, fx_rates: MagicMock
) -> None:
    currency_repo.find_by_code.return_value = None
    created = SimpleNamespace(id=1, code="EUR")
    currency_repo.create.return_value = created

    service.create(CurrencyCreateRequest(code="eur", exchange_rate=Decimal("1.08")))

    fx_rates.record_manual_rate_to_base.assert_called_once_with(
        created, Decimal("1.08")
    )


def test_create_without_a_rate_records_nothing(
    service: CurrencyService, currency_repo: MagicMock, fx_rates: MagicMock
) -> None:
    """The default 1 is a placeholder, not a quote: it must not become history."""
    currency_repo.find_by_code.return_value = None
    currency_repo.create.return_value = SimpleNamespace(id=1, code="EUR")

    service.create(CurrencyCreateRequest(code="eur"))

    fx_rates.record_manual_rate_to_base.assert_not_called()


def test_update_of_the_rate_records_it_as_a_manual_rate(
    service: CurrencyService, currency_repo: MagicMock, fx_rates: MagicMock
) -> None:
    currency = SimpleNamespace(id=1, code="EUR", exchange_rate=Decimal("1"))
    currency_repo.get_by_id.return_value = currency

    service.update(1, CurrencyUpdateRequest(exchange_rate=Decimal("1.1")))

    fx_rates.record_manual_rate_to_base.assert_called_once_with(
        currency, Decimal("1.1")
    )


def test_update_of_another_field_records_no_rate(
    service: CurrencyService, currency_repo: MagicMock, fx_rates: MagicMock
) -> None:
    currency = SimpleNamespace(
        id=1, code="EUR", exchange_rate=Decimal("1"), base_currency_id=None
    )
    currency_repo.get_by_id.return_value = currency
    currency_repo.find_by_code.return_value = None

    service.update(1, CurrencyUpdateRequest(code="eur"))

    fx_rates.record_manual_rate_to_base.assert_not_called()
