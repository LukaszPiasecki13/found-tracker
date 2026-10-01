"""Currency management."""

from sqlalchemy.exc import IntegrityError

from app.core.entities import apply_changes
from app.modules.assets.exceptions import (
    CurrencyAlreadyExistsError,
    CurrencyInUseError,
    UnknownBaseCurrencyError,
)
from app.modules.assets.models.currencies import Currency
from app.modules.assets.repositories.currencies import CurrencyRepository
from app.modules.assets.schemas.currencies import (
    CurrencyCreateRequest,
    CurrencyUpdateRequest,
)


class CurrencyService:
    """Currency CRUD; codes are unique and stored uppercase."""

    def __init__(self, repository: CurrencyRepository) -> None:
        self._repo = repository

    @staticmethod
    def _normalize_code(code: str) -> str:
        return code.strip().upper()

    def list_currencies(self) -> list[Currency]:
        return self._repo.list_all()

    def get_by_id(self, currency_id: int) -> Currency:
        """Raises CurrencyNotFoundError."""
        return self._repo.get_by_id(currency_id)

    def find_by_id(self, currency_id: int) -> Currency | None:
        return self._repo.find_by_id(currency_id)

    def create(self, data: CurrencyCreateRequest) -> Currency:
        code = self._normalize_code(data.code)
        try:
            with self._repo.transaction():
                if self._repo.find_by_code(code):
                    raise CurrencyAlreadyExistsError
                if data.base_currency_id is not None:
                    self._require_base_currency(data.base_currency_id)
                return self._repo.create(
                    code=code,
                    exchange_rate=data.exchange_rate,
                    base_currency_id=data.base_currency_id,
                )
        except IntegrityError as err:
            self._raise_if_code_taken(code, err)
            raise

    def update(self, currency_id: int, data: CurrencyUpdateRequest) -> Currency:
        values = data.model_dump(exclude_unset=True)
        if "code" in values:
            values["code"] = self._normalize_code(values["code"])
        try:
            with self._repo.transaction():
                currency = self._repo.get_by_id(currency_id)
                if "code" in values:
                    duplicate = self._repo.find_by_code(values["code"])
                    if duplicate and duplicate.id != currency.id:
                        raise CurrencyAlreadyExistsError
                if values.get("base_currency_id") is not None:
                    self._require_base_currency(values["base_currency_id"])
                apply_changes(currency, values)
                return self._repo.update(currency)
        except IntegrityError as err:
            if "code" in values:
                self._raise_if_code_taken(values["code"], err, other_than=currency_id)
            raise

    def delete(self, currency_id: int) -> None:
        """Delete a currency nothing references (assets, portfolios, currencies)."""
        try:
            with self._repo.transaction():
                self._repo.delete(self._repo.get_by_id(currency_id))
        except IntegrityError as err:
            raise CurrencyInUseError from err

    def get_or_create_by_code(self, code: str) -> Currency:
        """Existing currency with this code, or a new one at rate 1 (flushed, has
        an id).

        No-commit core — transaction belongs to caller.
        """
        code = self._normalize_code(code)
        currency = self._repo.find_by_code(code)
        if currency is None:
            currency = self._repo.create(code=code)
        return currency

    def _require_base_currency(self, base_currency_id: int) -> None:
        if self._repo.find_by_id(base_currency_id) is None:
            raise UnknownBaseCurrencyError

    def _raise_if_code_taken(
        self, code: str, err: IntegrityError, *, other_than: int | None = None
    ) -> None:
        """After a failed commit: a concurrent writer took the code first."""
        existing = self._repo.find_by_code(code)
        if existing is not None and existing.id != other_than:
            raise CurrencyAlreadyExistsError from err
