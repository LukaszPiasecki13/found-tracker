---
id: be-assets-module
status: current
last_reviewed: 2026-10-01
type: mixed
scope: backend/assets
applies_to:
  - backend/app/modules/assets/**
  - backend/app/core/market_data.py
  - backend/app/infrastructure/market_data/**
---

# Moduł `assets`

Walory, klasy waloru, waluty oraz dane rynkowe (ceny i kursy z Yahoo Finance). Dane referencyjne, na których buduje [`portfolios`](./05_portfolios_module.md). Słownik: [`CONTEXT.md`](../../business/CONTEXT.md).

## 1. Model danych

| Tabela | Encja | Pola |
|---|---|---|
| `assets_assetclass` | `AssetClass` | `id`, `name` (unikalna, max 20) |
| `assets_currency` | `Currency` | `id`, `code` (unikalny, 3), `exchange_rate` (`Numeric(18,9)`), `base_currency_id` |
| `assets_asset` | `Asset` | `id`, `ticker` (unikalny), `name`, `asset_class_id`, `currency_id`, `current_price` (`Numeric(18,9)`), `exchange`, `sector`, `updated_at` |

Modele w stylu `Mapped[...]`/`mapped_column`; kwoty i kursy to `Decimal` ([ADR-0010](../adr/0010-decimal-i-precyzja-pieniedzy.md)).

## 2. Endpointy

Wszystkie wymagają zalogowanego użytkownika (`get_current_user`). Parametry ścieżki mają konwerter `:int`, więc statyczne ścieżki (`/assets/asset-classes`, `/assets/currencies`, `/assets/search-yahoo`) nigdy nie trafiają do `/{id}`, niezależnie od kolejności routerów.

| Metoda i ścieżka | Opis |
|---|---|
| `GET/POST /assets/asset-classes`, `PUT/PATCH/DELETE /assets/asset-classes/{id}` | CRUD klas waloru |
| `GET/POST /assets/currencies`, `GET/PUT/PATCH/DELETE /assets/currencies/{id}` | CRUD walut |
| `GET /assets/?search=`, `POST /assets/` | Lista (filtr po tickerze/nazwie) i utworzenie waloru |
| `GET/PUT/PATCH/DELETE /assets/{id}` | Walor (GET zwraca szczegóły z klasą i walutą) |
| `GET /assets/search-yahoo?q=` | `{"local": [...], "yahoo": [...]}` — lokalne walory (max 10) + trafienia dostawcy, których jeszcze nie ma lokalnie |
| `POST /assets/create-from-yahoo` | Utworzenie waloru z danych dostawcy |

Odpowiedzi: `Decimal` serializowany w JSON jako liczba (`core.schemas.DecimalNumber`). Schematy żądań mają `extra="forbid"`.

## 3. Reguły biznesowe

- **Normalizacja** w serwisie: ticker `strip().upper()`, kod waluty `strip().upper()`; nazwa klasy — dokładne dopasowanie.
- **Unikalność** tickera, kodu waluty i nazwy klasy sprawdzana przy tworzeniu i edycji; wyścig rozstrzyga `IntegrityError` tłumaczony na ten sam `ConflictError`.
- **Referencje w treści żądania** (`asset_class_id`, `currency_id`, `base_currency_id`) do nieistniejących wierszy → 400; zasób z adresu URL nie istnieje → 404.
- **Usunięcie** wiersza, do którego coś się odwołuje (walor w pozycji/operacji, klasa z walorami, waluta z walorami/portfelami) → 409 `*_IN_USE`.
- **Utworzenie z dostawcy:** klasa z `quoteType` (ETF→„ETF”, CRYPTOCURRENCY/CRYPTO→„Crypto”, MUTUALFUND→„Mutual Fund”, inaczej „Stock”), waluta z notowania (domyślnie USD); obie tworzone, gdy ich brak. Cena = pierwsza niezerowa z `currentPrice`, `regularMarketPrice`, `previousClose`.
- **Dane rynkowe są zależnością zewnętrzną:** błąd pobrania to sytuacja normalna. Wyszukiwanie przy awarii dostawcy zwraca pustą listę. Odświeżanie cen (`refresh_asset_prices`) i kursów (`refresh_currency_rates`, waluta bazowa = 1) jest best-effort per pozycja: błąd jednego tickera/waluty jest logowany i pomijany, nie przerywa reszty.

### Kody błędów

| Status | `code` |
|---|---|
| 404 | `ASSET_NOT_FOUND`, `ASSET_CLASS_NOT_FOUND`, `CURRENCY_NOT_FOUND`, `ASSET_NOT_FOUND_ON_PROVIDER` |
| 400 | `ASSET_CLASS_NOT_FOUND`, `CURRENCY_NOT_FOUND`, `BASE_CURRENCY_NOT_FOUND` (referencja w treści) |
| 409 | `ASSET_ALREADY_EXISTS`, `ASSET_CLASS_ALREADY_EXISTS`, `CURRENCY_ALREADY_EXISTS`, `ASSET_IN_USE`, `ASSET_CLASS_IN_USE`, `CURRENCY_IN_USE` |
| 502 | `MARKET_DATA_UNAVAILABLE` (awaria dostawcy przy imporcie) |

## 4. Dane rynkowe — port i adapter

Wzorem waterworks (`core/audit.py` jako port, `infrastructure/storage/` jako adapter):

| Element | Plik | Rola |
|---|---|---|
| Port | `core/market_data.py` | `Quote` (dataclass), `MarketDataProvider` (`Protocol`: `fetch_quote`, `fetch_fx_rate`, `fetch_close_history` — `end` wyłączny), `MarketDataUnavailableError` (502) |
| Adapter | `infrastructure/market_data/yahoo.py` | `YahooFinanceProvider` — jedyne miejsce importu `yfinance`; każdy wyjątek biblioteki/sieci → `MarketDataUnavailableError`; liczby przez `Decimal(str(x))` |
| Wybór adaptera | `assets/wiring.py` → `build_market_data_provider()` | Testy podmieniają tę funkcję (lub wstrzykują fałszywy provider), więc żaden test nie dotyka sieci |

`MarketDataService` zależy wyłącznie od portu. Dla `portfolios` wystawia `close_history(ticker, start, end)` i `current_price(ticker)` (komunikacja między modułami przez serwisy — [ADR-0006](../adr/0006-cross-module-wylacznie-przez-serwisy.md)).

## 5. Serwisy (API publiczne)

| Serwis | Metody |
|---|---|
| `AssetClassService` | `list_asset_classes`, `get_by_id`, `find_by_id`, `create`, `update`, `delete`; rdzeń bez commitu: `get_or_create_by_name` |
| `CurrencyService` | `list_currencies`, `get_by_id`, `find_by_id`, `create`, `update`, `delete`; rdzeń bez commitu: `get_or_create_by_code` |
| `AssetService` | `list_assets`, `get_by_id`, `find_by_id`, `find_by_ticker`, `search_local_and_provider` (read model), `create`, `update`, `delete`, `create_from_provider`; rdzeń bez commitu: `get_or_create_by_ticker(ticker, *, asset_class_name, currency_id)` |
| `MarketDataService` | `search`, `get_quote`, `current_price`, `close_history`, `refresh_asset_prices`, `refresh_currency_rates` |

Rdzenie bez commitu ([ADR-0008](../adr/0008-rdzenie-bez-commitu-w-operacjach-wielomodulowych.md)) służą `portfolios` przy rejestrowaniu operacji na nowym tickerze — transakcję trzyma orkiestrator.

## 6. Układ

```text
assets/
├─ api/{asset_classes,assets,currencies}.py   # __init__.py: wspólny `router` dla main.py
├─ services/{asset_classes,assets,currencies,market_data}.py
├─ repositories/{asset_classes,assets,currencies}.py
├─ schemas/{asset_classes,assets,currencies}.py
├─ models/{asset_classes,assets,currencies}.py
├─ constants.py  exceptions.py  dependencies.py  wiring.py
└─ tests/{unit,integration}/  fakes.py (FakeMarketDataProvider)
```

Moduł nie ma `domain/` — to CRUD plus I/O (DOM-7) — ani `entrypoints.py`, bo nie ma jeszcze wywołań spoza HTTP.

## 7. Stan vs cel

| Element | Stan | Cel | Krok |
|---|---|---|---|
| Struktura, wiring, błędy z `code`, `transaction()`, `find_`/`get_`, testy `unit/` + `integration/` | zgodne z celem | — | R-04 (domknięty) |
| Odświeżanie kursów/cen w tle | wywoływane synchronicznie w `GET /portfolios/positions` | `assets/entrypoints.py` (`refresh_currency_rates`) + driver (harmonogram), gdy powstanie | — (poza planem) |
